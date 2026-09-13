"""
PS69 Weather Analytics - Phase 5: Reports Routes
POST /reports: Citizen report submission with synchronous pipeline processing
GET /reports/{report_id}/status: Track own report status

SYNCHRONOUS PROCESSING MODEL:
All pipeline steps execute synchronously within the endpoint:
1. Validate input
2. Create WeatherReport from Phase 1-4C schema
3. Run Phase 3A normalization
4. Run Phase 3A deduplication
5. Correlate with existing events (spatial + temporal)
6. Score evidence with Phase 3C verification_engine
7. Create/update WeatherEvent
8. Store in PostgreSQL
9. Return complete response (no background jobs)
"""

import sys
import logging
from pathlib import Path
from uuid import UUID
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func, cast
from geoalchemy2 import functions as geofuncs
from geoalchemy2 import Geography

# Import Phase 1-4C pipeline modules
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from schemas.weather_report import WeatherReport as Phase3AWeatherReport, EVENT_TYPES
from ingestion.report_normalizer import normalize_report
from ingestion.report_dedup import detect_duplicates
from ingestion.report_validators import validate_report
from corroboration.verification_engine import verify_report
from corroboration.report_correlator import correlate_report, build_default_evidence_sources

# Phase 5 database models
from backend.api.models import WeatherReport, WeatherEvent, AuditLog
from backend.api.schemas import (
    ReportSubmissionRequest,
    ReportSubmissionResponse,
    ReportStatusResponse,
    ReportListResponse,
)
from backend.api.db import get_db
from backend.api.auth.rbac import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def correlate_report_to_event(
    report: WeatherReport,
    db: Session,
) -> Optional[WeatherEvent]:
    """
    Correlate a newly created report with existing events using:
    - Event type match
    - Spatial proximity (within ~10 km using PostGIS ST_Distance_Sphere)
    - Temporal proximity (within 3 hours)
    
    Returns existing WeatherEvent to link to, or None if no match.
    """
    if not report.location or not report.event_type:
        logger.debug(f"Report {report.report_id}: No location or event_type, cannot correlate")
        return None
    
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=3)
        
        # Use PostGIS ST_Distance_Sphere for spatial proximity (~10 km = 10000 meters)
        distance_threshold = 10000  # meters
        
        candidates = db.execute(
            select(WeatherEvent).where(
                and_(
                    WeatherEvent.event_type == report.event_type,
                    WeatherEvent.start_time >= cutoff_time,
                    geofuncs.ST_DWithin(
                        cast(WeatherEvent.location, Geography),
                        cast(report.location, Geography),
                        distance_threshold
                    )
                )
            )
        ).scalars().all()
        
        if candidates:
            logger.info(
                f"Report {report.report_id}: Found {len(candidates)} matching event(s) "
                f"(type={report.event_type}, spatial proximity)"
            )
            # Return first/best matching event
            return candidates[0]
        
        logger.debug(
            f"Report {report.report_id}: No matching events "
            f"(type={report.event_type}, within 3h/10km)"
        )
        return None
    
    except Exception as e:
        logger.error(f"Error correlating report to event: {e}", exc_info=True)
        raise


@router.post(
    "",
    response_model=ReportSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_report(
    request: ReportSubmissionRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportSubmissionResponse:
    """
    Citizen report submission endpoint.
    
    SYNCHRONOUS processing - all steps execute within this request:
    
    1. Validate input
    2. Create WeatherReport from Phase 1-4C schema
    3. Validate (Phase 3A)
    4. Normalize (Phase 3A)
    5. Deduplicate (Phase 3A)
    6. Correlate with existing events (spatial + temporal)
    7. Score evidence with Phase 3C verification_engine
    8. Create/update WeatherEvent in PostgreSQL
    9. Log audit trail
    10. Return response with complete result
    
    Latency: ~1-3 seconds (endpoint blocks until database commit)
    
    Returns:
    {
        "report_id": "...",
        "event_id": "...",
        "evidence_status": "SUPPORTED|CONFLICTING|UNVERIFIED|INSUFFICIENT_EVIDENCE",
        "evidence_support_score": 0.0-1.0 or null,
        "verification_status": "UNVERIFIED|VERIFIED|REJECTED|SUSPICIOUS",
        "created_at": "ISO 8601 timestamp"
    }
    """
    try:
        # ====== STEP 1: Create Phase 1-4C WeatherReport from input ======
        now = datetime.now(timezone.utc)
        
        # Build Phase 1-4C schema report
        phase3a_report = Phase3AWeatherReport(
            source_type="CITIZEN_REPORT",
            source_name="FastAPI_Phase5",
            author_id_or_hash=f"user:{current_user['user_id']}",
            timestamp=now.isoformat(),
            city=request.city,
            state=request.state,
            latitude=request.latitude,
            longitude=request.longitude,
            text=request.text,
            image_url=request.image_url,
            video_url=request.video_url,
            event_type=request.event_type if request.event_type in EVENT_TYPES else "OTHER",
            raw_event_type=request.event_type,
            raw_payload={
                "source": "fastapi_citizen_form",
                "submitted_by_user_id": str(current_user["user_id"]),
                "submission_timestamp": now.isoformat(),
            },
        )
        
        # ====== STEP 2: Validate (Phase 3A) ======
        phase3a_report = validate_report(phase3a_report)
        
        # ====== STEP 3: Normalize (Phase 3A) ======
        phase3a_report = normalize_report(phase3a_report)
        
        # ====== STEP 4: Deduplicate (Phase 3A) ======
        # Check if this exact report already exists
        detect_duplicates([phase3a_report])
        
        # Create database WeatherReport
        db_report = WeatherReport(
            report_id=UUID(phase3a_report.report_id),
            source_type=phase3a_report.source_type,
            source_name=phase3a_report.source_name,
            author_id_or_hash=phase3a_report.author_id_or_hash,
            report_timestamp=datetime.fromisoformat(phase3a_report.timestamp) if phase3a_report.timestamp else None,
            city=phase3a_report.city,
            state=phase3a_report.state,
            text=phase3a_report.text,
            image_url=phase3a_report.image_url,
            video_url=phase3a_report.video_url,
            event_type=phase3a_report.event_type,
            raw_event_type=phase3a_report.raw_event_type,
            verification_status=phase3a_report.verification_status,
            source_reliability=phase3a_report.source_reliability,
            is_duplicate=phase3a_report.is_duplicate,
            duplicate_hash=phase3a_report.duplicate_hash,
            is_suspicious=phase3a_report.is_suspicious,
            semantic_similarity_score=phase3a_report.semantic_similarity_score,
            predicted_event_category=phase3a_report.predicted_event_category,
            event_classification_confidence=phase3a_report.event_classification_confidence,
            risk_score=phase3a_report.risk_score,
            risk_label=phase3a_report.risk_label,
            raw_payload=phase3a_report.raw_payload,
        )
        
        # Set location if provided
        if request.latitude is not None and request.longitude is not None:
            from geoalchemy2 import WKTElement
            location_wkt = f"POINT({request.longitude} {request.latitude})"
            db_report.location = WKTElement(location_wkt, srid=4326)
        
        # Add to session but don't commit yet
        db.add(db_report)
        db.flush()  # Get the report in the session for FK references
        
        # ====== STEP 6: Correlate with existing events (spatial + temporal) ======
        matched_event = correlate_report_to_event(db_report, db)
        
        evidence_status = "UNVERIFIED"
        evidence_score = None
        evidence_detail = {}
        
        if matched_event:
            # Link report to existing event
            db_report.event_id = matched_event.event_id
            matched_event.member_report_ids.append(db_report.report_id)
            matched_event.report_count += 1
            evidence_status = matched_event.evidence_status or "UNVERIFIED"
            evidence_score = matched_event.evidence_support_score
            evidence_detail = matched_event.evidence_detail or {}
            logger.info(f"Report {db_report.report_id} linked to existing event {matched_event.event_id}")
        else:
            # Create new WeatherEvent
            new_event = WeatherEvent(
                event_type=db_report.event_type or "OTHER",
                location_name=f"{db_report.city}, {db_report.state}" if db_report.city else "Unknown",
                severity="MEDIUM",  # Default
                evidence_status="UNVERIFIED",  # Will be scored by Phase 3C
                evidence_support_score=None,
                evidence_detail={},
                final_verification_status="NEEDS_REVIEW",
                member_report_ids=[db_report.report_id],
                report_count=1,
                unique_sources=1,
                start_time=db_report.report_timestamp or datetime.now(timezone.utc),
            )
            
            # Set location if available
            if request.latitude is not None and request.longitude is not None:
                from geoalchemy2 import WKTElement
                location_wkt = f"POINT({request.longitude} {request.latitude})"
                new_event.location = WKTElement(location_wkt, srid=4326)
            
            db.add(new_event)
            db.flush()  # Get event ID
            
            db_report.event_id = new_event.event_id
            evidence_status = "UNVERIFIED"
            logger.info(f"Report {db_report.report_id} created new event {new_event.event_id}")
        
        # ====== STEP 7: Call Phase 3C verification_engine for evidence scoring ======
        try:
            # Load the actual Phase 3C evidence sources (ERA5, Open-Meteo, IMD)
            # This loads real weather data from Phase 2B/2C
            evidence_sources = build_default_evidence_sources()
            
            if evidence_sources:
                # Correlate report with real evidence sources
                correlation_result = correlate_report(
                    phase3a_report,
                    evidence_sources,
                    max_time_diff_minutes=60,  # 1 hour temporal window
                    max_distance_km=50  # 50 km spatial window
                )
                
                if correlation_result and correlation_result.get("sources"):
                    # Call Phase 3C verification engine with correlation result
                    verification_result = verify_report(phase3a_report, correlation_result)
                    
                    if verification_result:
                        # Use actual Phase 3C verdict
                        evidence_status = verification_result.get("verification_status", "UNVERIFIED")
                        evidence_score = verification_result.get("evidence_support_score")
                        evidence_detail = {
                            "verification_status": evidence_status,
                            "evidence_support_score": evidence_score,
                            "evidence_sources": verification_result.get("evidence_sources", []),
                            "verification_reasons": verification_result.get("verification_reasons", []),
                            "source_evidence": verification_result.get("source_evidence", {}),
                        }
                        logger.info(
                            f"Report {db_report.report_id}: Phase 3C verification="
                            f"{evidence_status} (score={evidence_score}, "
                            f"sources={verification_result.get('evidence_sources', [])})"
                        )
                else:
                    # No matching evidence in any source -> INSUFFICIENT_EVIDENCE
                    evidence_status = "INSUFFICIENT_EVIDENCE"
                    evidence_score = None
                    logger.info(
                        f"Report {db_report.report_id}: No matching evidence in Phase 3C sources "
                        f"(timestamp={phase3a_report.timestamp}, lat={phase3a_report.latitude}, "
                        f"lon={phase3a_report.longitude})"
                    )
            else:
                # Phase 2B/2C evidence sources not available
                evidence_status = "INSUFFICIENT_EVIDENCE"
                evidence_score = None
                logger.warning(f"Phase 3C evidence sources unavailable for report {db_report.report_id}")
        
        except Exception as e:
            logger.error(
                f"Phase 3C verification failed for report {db_report.report_id}: {e}",
                exc_info=True,
            )
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Evidence verification failed; report was not stored.",
            )
        
        # Update event with evidence results
        if matched_event:
            matched_event.evidence_status = evidence_status
            matched_event.evidence_support_score = evidence_score
            matched_event.evidence_detail = evidence_detail
        else:
            new_event.evidence_status = evidence_status
            new_event.evidence_support_score = evidence_score
            new_event.evidence_detail = evidence_detail
        
        # ====== STEP 8: Add audit trail to the same transaction ======
        audit_entry = AuditLog(
            entity_type="WEATHER_REPORT",
            entity_id=db_report.report_id,
            action="CREATE",
            actor_id=UUID(current_user["user_id"]),
            changes={
                "report_id": str(db_report.report_id),
                "event_id": str(db_report.event_id),
                "event_type": db_report.event_type,
                "verification_status": db_report.verification_status,
            },
        )
        db.add(audit_entry)
        db.commit()
        
        logger.info(
            f"Report submitted: {db_report.report_id} "
            f"→ Event: {db_report.event_id} "
            f"(Evidence: {evidence_status})"
        )
        
        # ====== STEP 10: Return response ======
        return ReportSubmissionResponse(
            report_id=db_report.report_id,
            event_id=db_report.event_id,
            evidence_status=evidence_status,
            evidence_support_score=evidence_score,
            verification_status=db_report.verification_status,
            created_at=db_report.created_at,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error submitting report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing report: {str(e)}",
        )


@router.get("/{report_id}/status", response_model=ReportStatusResponse)
def get_report_status(
    report_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportStatusResponse:
    """
    Get report status and evidence information.
    
    Authorization: Citizen can access own report, analyst/admin can access all.
    
    Returns:
    - Report metadata (text, location, type, source)
    - Verification status (Phase 3A: UNVERIFIED/VERIFIED/REJECTED/SUSPICIOUS)
    - Evidence status (Phase 3C: SUPPORTED/CONFLICTING/UNVERIFIED/INSUFFICIENT_EVIDENCE)
    - Evidence support score (0.0-1.0) from Phase 3C verification
    """
    # Find report
    report = db.execute(
        select(WeatherReport).where(WeatherReport.report_id == report_id)
    ).scalars().first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    
    # Authorization check: Citizens can only view their own reports
    if current_user["role"] == "CITIZEN":
        # Citizens can only view their own reports
        if str(report.author_id_or_hash) != f"user:{current_user['user_id']}":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this report",
            )
    
    # Fetch linked event to get evidence status and score

    event_evidence_status = None
    event_evidence_score = None
    event_final_verification_status = None
    
    if report.event_id:
        event = db.execute(
            select(WeatherEvent).where(WeatherEvent.event_id == report.event_id)
        ).scalars().first()
        
        if event:
            event_evidence_status = event.evidence_status
            event_evidence_score = event.evidence_support_score
            event_final_verification_status = event.final_verification_status
    
    return ReportStatusResponse(
        report_id=report.report_id,
        source_type=report.source_type,
        text=report.text,
        city=report.city,
        state=report.state,
        event_type=report.event_type,
        verification_status=report.verification_status,
        evidence_status=event_evidence_status,
        evidence_support_score=event_evidence_score,
        final_verification_status=event_final_verification_status,
        created_at=report.created_at,
        updated_at=report.updated_at,
        event_id=report.event_id,
    )


# ============================================================================
# PHASE 7: GET /reports/me — the citizen "My Reports" view.
#
# WHY THIS WAS ADDED: the frontend needs a real, backend-driven way to list a
# user's own submitted reports. Phase 5 only exposed POST /reports and
# GET /reports/{id}/status (single-report lookup), with no list endpoint.
# Rather than fabricate this data in the frontend (or track it client-side in
# localStorage, which would break across devices/browsers and isn't
# real backend state), this endpoint was added.
#
# WHAT WAS CHANGED / WHAT WASN'T:
# - No database schema change: WeatherReport.author_id_or_hash already encodes
#   the submitting user as f"user:{user_id}" (set in submit_report above), and
#   get_report_status already relies on exact-matching that same string for
#   its own-report authorization check. This endpoint reuses that exact
#   convention rather than introducing a new column or migration.
# - No existing route, schema, or model was modified. ReportListResponse
#   (schemas.py) and this function are additive; they reuse ReportStatusResponse
#   per item instead of duplicating its fields.
# - Authorization follows the same model already used elsewhere in this file:
#   any authenticated user (CITIZEN/ANALYST/ADMIN) may call this endpoint, and
#   it always returns only *that caller's own* reports — there is no
#   "list everyone's reports" mode here, so no new privilege is introduced.
# - Real PostgreSQL pagination (limit/offset) plus a total count, following the
#   same limit/offset/total shape already used by GET /events and
#   GET /admin/verification-queue.
# ============================================================================

@router.get("/me", response_model=ReportListResponse)
def list_my_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportListResponse:
    """
    List the authenticated user's own submitted reports, newest first.

    Authorization: always scoped to the caller (str(author_id_or_hash) ==
    f"user:{current_user['user_id']}"), for every role. There is no
    cross-user listing here.
    """
    author_key = f"user:{current_user['user_id']}"

    count_query = (
        select(func.count())
        .select_from(WeatherReport)
        .where(WeatherReport.author_id_or_hash == author_key)
    )
    total = db.execute(count_query).scalar_one()

    reports = db.execute(
        select(WeatherReport)
        .where(WeatherReport.author_id_or_hash == author_key)
        .order_by(WeatherReport.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    # Batch-fetch linked events in one query to avoid N+1 lookups.
    event_ids = [r.event_id for r in reports if r.event_id is not None]
    events_by_id = {}
    if event_ids:
        linked_events = db.execute(
            select(WeatherEvent).where(WeatherEvent.event_id.in_(event_ids))
        ).scalars().all()
        events_by_id = {e.event_id: e for e in linked_events}

    items = []
    for r in reports:
        linked_event = events_by_id.get(r.event_id) if r.event_id else None
        items.append(
            ReportStatusResponse(
                report_id=r.report_id,
                source_type=r.source_type,
                text=r.text,
                city=r.city,
                state=r.state,
                event_type=r.event_type,
                verification_status=r.verification_status,
                evidence_status=linked_event.evidence_status if linked_event else None,
                evidence_support_score=linked_event.evidence_support_score if linked_event else None,
                final_verification_status=linked_event.final_verification_status if linked_event else None,
                created_at=r.created_at,
                updated_at=r.updated_at,
                event_id=r.event_id,
            )
        )

    return ReportListResponse(reports=items, total=total, limit=limit, offset=offset)
