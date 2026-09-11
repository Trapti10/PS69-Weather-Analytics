"""
PS69 Weather Analytics - Phase 5: Events Routes
GET /events: Query events with role-based filtering
GET /events/{event_id}: Get event detail

Role-scoped visibility:
- CITIZEN: See only VERIFIED events
- ANALYST/ADMIN: See all events
"""

import logging
from uuid import UUID
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.api.models import WeatherEvent
from backend.api.schemas import EventResponse, EventListResponse
from backend.api.db import get_db
from backend.api.auth.rbac import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=EventListResponse)
def list_events(
    status_filter: Optional[str] = Query(None, alias="status"),
    evidence_status: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventListResponse:
    """
    List events with role-based filtering.
    
    Filtering:
    - status: VERIFIED|NEEDS_REVIEW|REJECTED (final_verification_status)
    - evidence_status: SUPPORTED|CONFLICTING|UNVERIFIED|INSUFFICIENT_EVIDENCE
    - event_type: event category
    - severity: LOW|MEDIUM|HIGH|EXTREME
    - city: Filter by city
    - start_date/end_date: start_time range
    
    Authorization:
    - CITIZEN: only final_verification_status=VERIFIED
    - ANALYST/ADMIN: all statuses
    """
    query = select(WeatherEvent)
    
    # Role-based visibility
    if current_user["role"] == "CITIZEN":
        # Citizens only see verified events
        query = query.where(WeatherEvent.final_verification_status == "VERIFIED")
    
    # Apply filters
    if status_filter:
        valid_statuses = {"VERIFIED", "NEEDS_REVIEW", "REJECTED"}
        if status_filter in valid_statuses:
            if current_user["role"] != "CITIZEN":  # Citizens can't filter to unverified
                query = query.where(WeatherEvent.final_verification_status == status_filter)
    
    if evidence_status and evidence_status in {"SUPPORTED", "CONFLICTING", "UNVERIFIED", "INSUFFICIENT_EVIDENCE"}:
        query = query.where(WeatherEvent.evidence_status == evidence_status)

    if event_type:
        query = query.where(WeatherEvent.event_type == event_type)

    if severity and severity in {"LOW", "MEDIUM", "HIGH", "EXTREME"}:
        query = query.where(WeatherEvent.severity == severity)

    if city:
        query = query.where(WeatherEvent.location_name.like(f"%{city}%"))

    if start_date:
        query = query.where(WeatherEvent.start_time >= start_date)

    if end_date:
        query = query.where(WeatherEvent.start_time <= end_date)
    
    # Get total count using the same filtered query (before pagination).
    count_query = select(func.count()).select_from(WeatherEvent)
    if current_user["role"] == "CITIZEN":
        count_query = count_query.where(WeatherEvent.final_verification_status == "VERIFIED")
    if status_filter and status_filter in {"VERIFIED", "NEEDS_REVIEW", "REJECTED"} and current_user["role"] != "CITIZEN":
        count_query = count_query.where(WeatherEvent.final_verification_status == status_filter)
    if evidence_status and evidence_status in {"SUPPORTED", "CONFLICTING", "UNVERIFIED", "INSUFFICIENT_EVIDENCE"}:
        count_query = count_query.where(WeatherEvent.evidence_status == evidence_status)
    if event_type:
        count_query = count_query.where(WeatherEvent.event_type == event_type)
    if severity and severity in {"LOW", "MEDIUM", "HIGH", "EXTREME"}:
        count_query = count_query.where(WeatherEvent.severity == severity)
    if city:
        count_query = count_query.where(WeatherEvent.location_name.like(f"%{city}%"))
    if start_date:
        count_query = count_query.where(WeatherEvent.start_time >= start_date)
    if end_date:
        count_query = count_query.where(WeatherEvent.start_time <= end_date)
    total_count = db.execute(count_query).scalar_one()
    
    # Apply pagination
    events = db.execute(
        query.order_by(WeatherEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    # Phase 7: batch-extract lon/lat for every event in this page in a single
    # query (avoids N+1 ST_X/ST_Y calls). WeatherEvent.location is already
    # populated at submission time (routes/reports.py) when coordinates were
    # provided; this only reads it, no schema change.
    event_ids = [e.event_id for e in events]
    coords_by_id: dict = {}
    if event_ids:
        coord_rows = db.execute(
            select(
                WeatherEvent.event_id,
                func.ST_X(WeatherEvent.location),
                func.ST_Y(WeatherEvent.location),
            ).where(WeatherEvent.event_id.in_(event_ids))
        ).all()
        coords_by_id = {row[0]: (row[1], row[2]) for row in coord_rows}

    return EventListResponse(
        events=[
            _event_to_response(e, *coords_by_id.get(e.event_id, (None, None)))
            for e in events
        ],
        total=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventResponse:
    """
    Get event detail with evidence information.
    
    Authorization:
    - CITIZEN: only if final_verification_status=VERIFIED
    - ANALYST/ADMIN: all events
    """
    event = db.execute(
        select(WeatherEvent).where(WeatherEvent.event_id == event_id)
    ).scalars().first()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    
    # Check authorization
    if current_user["role"] == "CITIZEN":
        if event.final_verification_status != "VERIFIED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this event",
            )
    
    longitude, latitude = db.execute(
        select(func.ST_X(WeatherEvent.location), func.ST_Y(WeatherEvent.location)).where(
            WeatherEvent.event_id == event_id
        )
    ).first() or (None, None)

    return _event_to_response(event, longitude, latitude)


def _event_to_response(event: WeatherEvent, longitude: Optional[float] = None, latitude: Optional[float] = None) -> EventResponse:
    """Convert database WeatherEvent to response schema.

    longitude/latitude are passed in separately (extracted via ST_X/ST_Y in the
    same query as the event, see list_events/get_event) rather than re-queried
    per row, to avoid N+1 PostGIS calls.
    """
    return EventResponse(
        event_id=event.event_id,
        event_type=event.event_type,
        location_name=event.location_name,
        severity=event.severity,
        start_time=event.start_time,
        end_time=event.end_time,
        latitude=latitude,
        longitude=longitude,
        evidence_status=event.evidence_status,
        evidence_support_score=event.evidence_support_score,
        evidence_detail=event.evidence_detail,
        final_verification_status=event.final_verification_status,
        report_count=event.report_count,
        unique_sources=event.unique_sources,
        member_report_ids=event.member_report_ids or [],
        reviewed_by=event.reviewed_by,
        reviewed_at=event.reviewed_at,
        review_notes=event.review_notes,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )
