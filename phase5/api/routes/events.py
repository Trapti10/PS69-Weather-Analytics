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

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from phase5.api.models import WeatherEvent
from phase5.api.schemas import EventResponse, EventListResponse
from phase5.api.db import get_db
from phase5.api.auth.rbac import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=EventListResponse)
def list_events(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventListResponse:
    """
    List events with role-based filtering.
    
    Filtering:
    - status: VERIFIED|NEEDS_REVIEW|REJECTED (final_verification_status)
    - severity: LOW|MEDIUM|HIGH|EXTREME
    - city: Filter by city
    
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
    
    if severity and severity in {"LOW", "MEDIUM", "HIGH", "EXTREME"}:
        query = query.where(WeatherEvent.severity == severity)
    
    if city:
        query = query.where(WeatherEvent.location_name.like(f"%{city}%"))
    
    # Get total count using the same filtered query (before pagination).
    count_query = select(func.count()).select_from(WeatherEvent)
    if current_user["role"] == "CITIZEN":
        count_query = count_query.where(WeatherEvent.final_verification_status == "VERIFIED")
    if status_filter and status_filter in {"VERIFIED", "NEEDS_REVIEW", "REJECTED"} and current_user["role"] != "CITIZEN":
        count_query = count_query.where(WeatherEvent.final_verification_status == status_filter)
    if severity and severity in {"LOW", "MEDIUM", "HIGH", "EXTREME"}:
        count_query = count_query.where(WeatherEvent.severity == severity)
    if city:
        count_query = count_query.where(WeatherEvent.location_name.like(f"%{city}%"))
    total_count = db.execute(count_query).scalar_one()
    
    # Apply pagination
    events = db.execute(
        query.order_by(WeatherEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()
    
    return EventListResponse(
        events=[_event_to_response(e) for e in events],
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
    
    return _event_to_response(event)


def _event_to_response(event: WeatherEvent) -> EventResponse:
    """Convert database WeatherEvent to response schema."""
    return EventResponse(
        event_id=event.event_id,
        event_type=event.event_type,
        location_name=event.location_name,
        severity=event.severity,
        start_time=event.start_time,
        end_time=event.end_time,
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
