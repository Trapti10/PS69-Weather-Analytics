"""
PS69 Weather Analytics - Phase 6: Admin Verification Workflow
GET  /admin/verification-queue          : Paginated queue of events awaiting/under review
GET  /admin/events/{event_id}/evidence  : Full evidence package for one event
POST /admin/events/{event_id}/verify    : Admin submits a final verification decision

Built entirely on top of the existing Phase 5 schema. No Phase 1-5 model, route,
or schema is modified — WeatherEvent.final_verification_status/reviewed_by/
reviewed_at/review_notes, AdminReviewAction, and AuditLog already existed in
Phase 5 and are reused as-is.

Evidence Status (system-assigned, Phase 3C) and Final Verification Status
(admin-assigned) are kept strictly separate throughout this module. This
endpoint set never derives one from the other.
"""

import logging
from uuid import UUID
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_

from phase5.api.models import WeatherEvent, WeatherReport, AdminReviewAction, AuditLog
from phase5.api.schemas import (
    AdminReviewRequest,
    AdminQueueEntry,
    AdminQueueResponse,
    EvidenceReportItem,
    EvidenceEventSummary,
    EvidenceDetailResponse,
    AdminVerifyResponse,
)
from phase5.api.db import get_db
from phase5.api.auth.rbac import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_FINAL_STATUSES = {"VERIFIED", "NEEDS_REVIEW", "REJECTED"}
VALID_EVIDENCE_STATUSES = {"SUPPORTED", "CONFLICTING", "UNVERIFIED", "INSUFFICIENT_EVIDENCE"}
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "EXTREME"}

# Decisions that must carry a non-empty reason/comment (section 7 of the brief).
STATUSES_REQUIRING_REASON = {"REJECTED", "NEEDS_REVIEW"}


@router.get("/verification-queue", response_model=AdminQueueResponse)
def get_verification_queue(
    status_filter: Optional[str] = Query(
        "NEEDS_REVIEW",
        alias="status",
        description="Filter by final_verification_status. Use 'ALL' to see every status.",
    ),
    evidence_status: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None, description="Event category, e.g. RAINFALL, FLOODING"),
    city: Optional[str] = Query(None, description="Substring match against location_name"),
    severity: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None, description="Only events with start_time >= this"),
    end_date: Optional[datetime] = Query(None, description="Only events with start_time <= this"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminQueueResponse:
    """
    Admin-only. Retrieve events that require (or have received) admin review.

    Defaults to final_verification_status=NEEDS_REVIEW (the actual "queue").
    Pass status=ALL to browse VERIFIED/REJECTED history too, or status=VERIFIED /
    status=REJECTED to look at a specific bucket.

    evidence_status is a completely separate axis (system-assigned, Phase 3C) and
    can be combined with any final-status filter — e.g. status=NEEDS_REVIEW&
    evidence_status=CONFLICTING to find the cases most in need of human judgement.
    """
    filters = []

    if status_filter and status_filter.upper() != "ALL":
        if status_filter not in VALID_FINAL_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status filter. Must be one of {sorted(VALID_FINAL_STATUSES)} or 'ALL'.",
            )
        filters.append(WeatherEvent.final_verification_status == status_filter)

    if evidence_status:
        if evidence_status not in VALID_EVIDENCE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid evidence_status filter. Must be one of {sorted(VALID_EVIDENCE_STATUSES)}.",
            )
        filters.append(WeatherEvent.evidence_status == evidence_status)

    if event_type:
        filters.append(WeatherEvent.event_type == event_type)

    if city:
        filters.append(WeatherEvent.location_name.like(f"%{city}%"))

    if severity:
        if severity not in VALID_SEVERITIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid severity filter. Must be one of {sorted(VALID_SEVERITIES)}.",
            )
        filters.append(WeatherEvent.severity == severity)

    if start_date:
        filters.append(WeatherEvent.start_time >= start_date)

    if end_date:
        filters.append(WeatherEvent.start_time <= end_date)

    base_condition = and_(*filters) if filters else None

    count_query = select(func.count()).select_from(WeatherEvent)
    query = select(WeatherEvent)
    if base_condition is not None:
        count_query = count_query.where(base_condition)
        query = query.where(base_condition)

    total = db.execute(count_query).scalar_one()

    events = db.execute(
        query.order_by(WeatherEvent.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()

    items = [
        AdminQueueEntry(
            event_id=e.event_id,
            event_type=e.event_type,
            location_name=e.location_name,
            severity=e.severity,
            start_time=e.start_time,
            evidence_status=e.evidence_status,
            evidence_support_score=e.evidence_support_score,
            final_verification_status=e.final_verification_status,
            report_count=e.report_count or 0,
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
        for e in events
    ]

    return AdminQueueResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/events/{event_id}/evidence", response_model=EvidenceDetailResponse)
def get_event_evidence(
    event_id: UUID,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> EvidenceDetailResponse:
    """
    Admin-only. Full evidence package for one event: the event summary, the
    Phase 3C external-evidence detail (ERA5/IMD/Open-Meteo agreement), and
    every member report that contributed to it.

    Single query for member reports (filtered by event_id) to avoid N+1.
    """
    event = db.execute(
        select(WeatherEvent).where(WeatherEvent.event_id == event_id)
    ).scalars().first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    reports = db.execute(
        select(WeatherReport).where(WeatherReport.event_id == event_id)
    ).scalars().all()

    return EvidenceDetailResponse(
        event=EvidenceEventSummary(
            event_id=event.event_id,
            event_type=event.event_type,
            location_name=event.location_name,
            severity=event.severity,
            start_time=event.start_time,
            end_time=event.end_time,
            evidence_status=event.evidence_status,
            evidence_support_score=event.evidence_support_score,
            final_verification_status=event.final_verification_status,
            report_count=event.report_count or 0,
            unique_sources=event.unique_sources or 0,
        ),
        external_evidence=event.evidence_detail,
        reports=[
            EvidenceReportItem(
                report_id=r.report_id,
                source_type=r.source_type,
                source_name=r.source_name,
                author_id_or_hash=r.author_id_or_hash,
                report_timestamp=r.report_timestamp,
                city=r.city,
                state=r.state,
                text=r.text,
                event_type=r.event_type,
                verification_status=r.verification_status,
                source_reliability=r.source_reliability,
                predicted_event_category=r.predicted_event_category,
                event_classification_confidence=r.event_classification_confidence,
                risk_score=r.risk_score,
                risk_label=r.risk_label,
                semantic_similarity_score=r.semantic_similarity_score,
                is_duplicate=bool(r.is_duplicate),
                is_suspicious=bool(r.is_suspicious),
            )
            for r in reports
        ],
    )


@router.post("/events/{event_id}/verify", response_model=AdminVerifyResponse)
def verify_event(
    event_id: UUID,
    request: AdminReviewRequest,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminVerifyResponse:
    """
    Admin-only. Submit a final verification decision for an event.

    - action must be VERIFIED | NEEDS_REVIEW | REJECTED (enforced by
      AdminReviewRequest's pydantic pattern before this function even runs,
      so an invalid value is rejected with 422 automatically).
    - notes is required for REJECTED and NEEDS_REVIEW (a human reviewer should
      always be able to see *why* a case was rejected or bounced back).
    - reviewed_by is always the authenticated admin from the JWT — never taken
      from the request body.
    - Event update + AdminReviewAction + AuditLog are written in a single
      transaction: if anything fails, the event is not left updated without
      its audit trail.

    Evidence Status is never touched here. CONFLICTING evidence is not
    silently turned into REJECTED, and evidence records are never deleted -
    this endpoint only ever writes to final_verification_status and the two
    audit tables.
    """
    action = request.action
    notes = (request.notes or "").strip() or None

    if action in STATUSES_REQUIRING_REASON and not notes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"A reason/comment ('notes') is required when setting status to {action}.",
        )

    event = db.execute(
        select(WeatherEvent).where(WeatherEvent.event_id == event_id)
    ).scalars().first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    previous_status = event.final_verification_status
    admin_id = UUID(current_user["user_id"])
    now = datetime.utcnow()

    try:
        # 1. Update the event's final verification status (admin-owned field).
        event.final_verification_status = action
        event.reviewed_by = admin_id
        event.reviewed_at = now
        event.review_notes = notes

        # 2. Immutable admin decision record.
        evidence_summary = {
            "evidence_status": event.evidence_status,
            "evidence_support_score": event.evidence_support_score,
            "report_count": event.report_count,
            "unique_sources": event.unique_sources,
        }
        review_action = AdminReviewAction(
            event_id=event.event_id,
            admin_id=admin_id,
            action=action,
            notes=notes,
            evidence_summary=evidence_summary,
        )
        db.add(review_action)

        # 3. Generic audit trail (who / what / when / why).
        audit_entry = AuditLog(
            entity_type="WEATHER_EVENT",
            entity_id=event.event_id,
            action=action,
            actor_id=admin_id,
            changes={
                "previous_status": previous_status,
                "new_status": action,
                "notes": notes,
            },
        )
        db.add(audit_entry)

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(
            f"Error recording verification decision for event {event_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error recording verification decision; no changes were saved.",
        )

    logger.info(
        f"Admin {admin_id} set event {event_id} verification status: "
        f"{previous_status} -> {action}"
    )

    return AdminVerifyResponse(
        event_id=event.event_id,
        previous_status=previous_status,
        final_verification_status=action,
        reviewed_by=admin_id,
        reviewed_at=now,
        notes=notes,
    )
