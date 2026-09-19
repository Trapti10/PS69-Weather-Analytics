"""Role-safe location search and public weather-event summaries."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from backend.api.auth.rbac import get_current_user
from backend.api.db import get_db
from backend.api.models import WeatherAnomaly, WeatherEvent, WeatherObservation
from backend.api.schemas import (
    LocationSearchItem,
    LocationSearchResponse,
    PublicLocationEvent,
    PublicLocationSummaryResponse,
)

router = APIRouter()

# The scientific historical dataset is explicitly Jabalpur-focused. It has a
# source grid point at 23.25, 80.0 and no city field, so we name the coverage
# honestly rather than pretending the grid point represents a full district.
JABALPUR = ("Jabalpur, Madhya Pradesh", 23.25, 80.0)


def _event_projection(db: Session, name_filter: str):
    lat = func.ST_Y(WeatherEvent.location)
    lon = func.ST_X(WeatherEvent.location)
    rows = db.execute(
        select(
            WeatherEvent.event_id,
            WeatherEvent.event_type,
            WeatherEvent.location_name,
            WeatherEvent.severity,
            WeatherEvent.start_time,
            WeatherEvent.end_time,
            WeatherEvent.final_verification_status,
            lat,
            lon,
        )
        .where(func.lower(WeatherEvent.location_name).like(f"%{name_filter.lower()}%"))
        .order_by(WeatherEvent.start_time.desc())
        .limit(50)
    ).all()
    return [
        PublicLocationEvent(
            event_id=row[0],
            event_type=row[1],
            location_name=row[2],
            severity=row[3],
            start_time=row[4],
            end_time=row[5],
            final_verification_status=row[6],
        )
        for row in rows
    ]


@router.get("/search", response_model=LocationSearchResponse)
def search_locations(
    q: str = Query("", max_length=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LocationSearchResponse:
    normalized = q.strip().lower()
    results: list[LocationSearchItem] = []

    if not normalized or "jabalpur" in normalized or "madhya pradesh" in normalized:
        obs_count = db.execute(
            select(func.count(WeatherObservation.id)).where(
                and_(
                    WeatherObservation.latitude.between(22.75, 23.75),
                    WeatherObservation.longitude.between(79.5, 80.5),
                )
            )
        ).scalar_one()
        anomaly_count = db.execute(
            select(func.count(WeatherAnomaly.id)).where(
                and_(
                    WeatherAnomaly.latitude.between(22.75, 23.75),
                    WeatherAnomaly.longitude.between(79.5, 80.5),
                )
            )
        ).scalar_one()
        coverage = db.execute(
            select(func.min(WeatherObservation.observed_at), func.max(WeatherObservation.observed_at)).where(
                and_(
                    WeatherObservation.latitude.between(22.75, 23.75),
                    WeatherObservation.longitude.between(79.5, 80.5),
                )
            )
        ).one()
        event_count = db.execute(
            select(func.count(WeatherEvent.event_id)).where(
                func.lower(WeatherEvent.location_name).like("%jabalpur%")
            )
        ).scalar_one()
        results.append(
            LocationSearchItem(
                name=JABALPUR[0],
                latitude=JABALPUR[1],
                longitude=JABALPUR[2],
                observation_count=obs_count or 0,
                anomaly_count=anomaly_count or 0,
                event_count=event_count or 0,
                coverage_start=coverage[0],
                coverage_end=coverage[1],
            )
        )

    if normalized:
        event_rows = db.execute(
            select(
                WeatherEvent.location_name,
                func.count(WeatherEvent.event_id),
                func.max(func.ST_X(WeatherEvent.location)),
                func.max(func.ST_Y(WeatherEvent.location)),
                func.min(WeatherEvent.start_time),
                func.max(WeatherEvent.start_time),
            )
            .where(func.lower(WeatherEvent.location_name).like(f"%{normalized}%"))
            .group_by(WeatherEvent.location_name)
            .order_by(func.count(WeatherEvent.event_id).desc())
            .limit(10)
        ).all()
        for row in event_rows:
            if any(item.name.lower() == row[0].lower() for item in results if row[0]):
                continue
            results.append(
                LocationSearchItem(
                    name=row[0],
                    latitude=row[3],
                    longitude=row[2],
                    event_count=row[1],
                    coverage_start=row[4],
                    coverage_end=row[5],
                )
            )

    return LocationSearchResponse(locations=results[:10])


@router.get("/{location_name}/summary", response_model=PublicLocationSummaryResponse)
def location_summary(
    location_name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicLocationSummaryResponse:
    name = location_name.replace("%", "").strip()
    is_jabalpur = "jabalpur" in name.lower()

    if is_jabalpur:
        bounds = and_(
            WeatherObservation.latitude.between(22.75, 23.75),
            WeatherObservation.longitude.between(79.5, 80.5),
        )
        obs = db.execute(
            select(func.count(WeatherObservation.id), func.min(WeatherObservation.observed_at), func.max(WeatherObservation.observed_at)).where(bounds)
        ).one()
        anomalies = db.execute(
            select(func.count(WeatherAnomaly.id)).where(
                and_(
                    WeatherAnomaly.latitude.between(22.75, 23.75),
                    WeatherAnomaly.longitude.between(79.5, 80.5),
                )
            )
        ).scalar_one()
        events = _event_projection(db, "jabalpur")
        return PublicLocationSummaryResponse(
            location=JABALPUR[0],
            latitude=JABALPUR[1],
            longitude=JABALPUR[2],
            dataset_coverage_start=obs[1],
            dataset_coverage_end=obs[2],
            observation_count=obs[0] or 0,
            anomaly_count=anomalies or 0,
            events=events,
            note="Historical scientific coverage in this deployment is centered on the Jabalpur 23.25°N, 80.0°E source grid. Event status is based on the platform's structured WeatherEvent verification workflow.",
        )

    events = _event_projection(db, name)
    return PublicLocationSummaryResponse(
        location=name,
        observation_count=0,
        anomaly_count=0,
        events=events,
        note=("No scientific observation coverage is currently mapped to this location."
              if not events else "Showing weather events recorded for this location."),
    )
