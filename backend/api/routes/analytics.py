"""
PS69 Weather Analytics - Analytics Routes

Database-backed weather intelligence for the Analyst/Admin dashboards.

Every endpoint here does its aggregation in PostgreSQL (COUNT/AVG/SUM/MIN/MAX/
GROUP BY/date_trunc) and returns already-aggregated JSON - none of this loads
raw observation rows into Python for calculation, and none of it is ever sent
to the frontend as raw rows for client-side math.

Data sources:
- weather_observations / weather_anomalies: real ERA5 + Open-Meteo +
  Phase 4C data, populated by backend/db/ingest_analytics_data.py
  (see backend/db/schema.sql for provenance comments on both tables).
- weather_events: the existing citizen-report/verification pipeline
  (Phase 3-6), unchanged by this file.

Authorization: ANALYST and ADMIN only (require_analyst already allows both).
Citizen-facing analytics are intentionally NOT exposed here - the Citizen
dashboard consumes /reports and /events directly, not this router.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_

from backend.api.db import get_db
from backend.api.auth.rbac import require_analyst
from backend.api.models import WeatherObservation, WeatherAnomaly, WeatherEvent, WeatherReport
from backend.api.schemas import (
    AnalyticsOverviewResponse,
    WeatherTrendsResponse,
    WeatherTrendPoint,
    RainfallAnalyticsResponse,
    RainfallTrendPoint,
    TemperatureAnalyticsResponse,
    TemperatureTrendPoint,
    SourceComparisonResponse,
    SourceComparisonItem,
    AnomalyAnalyticsResponse,
    AnomalyVariableSeverityCount,
    AnomalySeverityCount,
    AnomalyItem,
    EventDistributionResponse,
    EventTypeCount,
    EventSeverityCount,
    VerificationAnalyticsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _observation_filters(
    source: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
):
    filters = []
    if source:
        filters.append(WeatherObservation.source == source)
    if start_date:
        filters.append(WeatherObservation.observed_at >= start_date)
    if end_date:
        filters.append(WeatherObservation.observed_at <= end_date)
    return filters


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_overview(
    current_user: dict = Depends(require_analyst),
    db: Session = Depends(get_db),
) -> AnalyticsOverviewResponse:
    """Top-line KPIs combining the observation/anomaly intelligence layer
    with the citizen-report/verification pipeline. Single round trip per
    table, all aggregation in SQL.
    """
    obs_row = db.execute(
        select(
            func.count(WeatherObservation.id),
            func.count(func.distinct(WeatherObservation.source)),
            func.avg(WeatherObservation.temperature),
            func.max(WeatherObservation.temperature),
            func.sum(WeatherObservation.rainfall),
            func.min(WeatherObservation.observed_at),
            func.max(WeatherObservation.observed_at),
        )
    ).one()
    (
        total_observations,
        total_sources,
        avg_temp,
        max_temp,
        total_rainfall,
        obs_start,
        obs_end,
    ) = obs_row

    total_anomalies = db.execute(select(func.count(WeatherAnomaly.id))).scalar_one()
    total_reports = db.execute(select(func.count(WeatherReport.report_id))).scalar_one()

    event_row = db.execute(
        select(
            func.count(WeatherEvent.event_id),
            func.count(WeatherEvent.event_id).filter(WeatherEvent.final_verification_status == "VERIFIED"),
            func.count(WeatherEvent.event_id).filter(WeatherEvent.final_verification_status == "NEEDS_REVIEW"),
            func.count(WeatherEvent.event_id).filter(WeatherEvent.final_verification_status == "REJECTED"),
        )
    ).one()
    total_events, verified, needs_review, rejected = event_row

    return AnalyticsOverviewResponse(
        total_weather_observations=total_observations or 0,
        total_weather_events=total_events or 0,
        total_reports=total_reports or 0,
        total_anomalies=total_anomalies or 0,
        total_sources=total_sources or 0,
        verified_events=verified or 0,
        needs_review=needs_review or 0,
        rejected_events=rejected or 0,
        average_temperature=round(avg_temp, 2) if avg_temp is not None else None,
        max_temperature=round(max_temp, 2) if max_temp is not None else None,
        total_rainfall=round(total_rainfall, 2) if total_rainfall is not None else None,
        observations_date_range_start=obs_start,
        observations_date_range_end=obs_end,
    )


@router.get("/weather-trends", response_model=WeatherTrendsResponse)
def get_weather_trends(
    source: Optional[str] = Query(None, description="Filter to a single source, e.g. ERA5 or Open-Meteo"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_analyst),
    db: Session = Depends(get_db),
) -> WeatherTrendsResponse:
    """Day-bucketed temperature/rainfall/humidity/wind trend, aggregated in SQL."""
    filters = _observation_filters(source, start_date, end_date)
    day = func.date_trunc("day", WeatherObservation.observed_at)

    rows = db.execute(
        select(
            day.label("day"),
            func.avg(WeatherObservation.temperature),
            func.sum(WeatherObservation.rainfall),
            func.avg(WeatherObservation.humidity),
            func.avg(WeatherObservation.wind_speed),
            func.avg(WeatherObservation.pressure),
            func.count(WeatherObservation.id),
        )
        .where(and_(*filters) if filters else True)
        .group_by(day)
        .order_by(day)
    ).all()

    trends = [
        WeatherTrendPoint(
            date=row[0].date().isoformat(),
            average_temperature=round(row[1], 2) if row[1] is not None else None,
            rainfall=round(row[2], 2) if row[2] is not None else None,
            average_humidity=round(row[3], 2) if row[3] is not None else None,
            average_wind_speed=round(row[4], 2) if row[4] is not None else None,
            average_pressure=round(row[5], 2) if row[5] is not None else None,
            observation_count=row[6],
        )
        for row in rows
    ]

    return WeatherTrendsResponse(trends=trends, source=source, start_date=start_date, end_date=end_date)


@router.get("/rainfall", response_model=RainfallAnalyticsResponse)
def get_rainfall_analytics(
    source: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_analyst),
    db: Session = Depends(get_db),
) -> RainfallAnalyticsResponse:
    """Day-bucketed total rainfall, plus overall total/max-day, aggregated in SQL."""
    filters = _observation_filters(source, start_date, end_date)
    day = func.date_trunc("day", WeatherObservation.observed_at)

    rows = db.execute(
        select(day.label("day"), func.sum(WeatherObservation.rainfall), func.count(WeatherObservation.id))
        .where(and_(*filters) if filters else True)
        .group_by(day)
        .order_by(day)
    ).all()

    trends = [
        RainfallTrendPoint(
            date=row[0].date().isoformat(),
            total_rainfall=round(row[1], 2) if row[1] is not None else None,
            observation_count=row[2],
        )
        for row in rows
    ]

    total_rainfall = sum(t.total_rainfall for t in trends if t.total_rainfall is not None) or 0.0
    max_daily = max((t.total_rainfall for t in trends if t.total_rainfall is not None), default=None)

    return RainfallAnalyticsResponse(
        trends=trends,
        total_rainfall=round(total_rainfall, 2),
        max_daily_rainfall=round(max_daily, 2) if max_daily is not None else None,
    )


@router.get("/temperature", response_model=TemperatureAnalyticsResponse)
def get_temperature_analytics(
    source: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_analyst),
    db: Session = Depends(get_db),
) -> TemperatureAnalyticsResponse:
    """Day-bucketed temperature avg/min/max, aggregated in SQL."""
    filters = _observation_filters(source, start_date, end_date)
    day = func.date_trunc("day", WeatherObservation.observed_at)

    rows = db.execute(
        select(
            day.label("day"),
            func.avg(WeatherObservation.temperature),
            func.min(WeatherObservation.temperature),
            func.max(WeatherObservation.temperature),
            func.count(WeatherObservation.id),
        )
        .where(and_(*filters) if filters else True)
        .group_by(day)
        .order_by(day)
    ).all()

    trends = [
        TemperatureTrendPoint(
            date=row[0].date().isoformat(),
            average_temperature=round(row[1], 2) if row[1] is not None else None,
            min_temperature=round(row[2], 2) if row[2] is not None else None,
            max_temperature=round(row[3], 2) if row[3] is not None else None,
            observation_count=row[4],
        )
        for row in rows
    ]

    overall = db.execute(
        select(
            func.avg(WeatherObservation.temperature),
            func.min(WeatherObservation.temperature),
            func.max(WeatherObservation.temperature),
        ).where(and_(*filters) if filters else True)
    ).one()

    return TemperatureAnalyticsResponse(
        trends=trends,
        average_temperature=round(overall[0], 2) if overall[0] is not None else None,
        min_temperature=round(overall[1], 2) if overall[1] is not None else None,
        max_temperature=round(overall[2], 2) if overall[2] is not None else None,
    )


@router.get("/source-comparison", response_model=SourceComparisonResponse)
def get_source_comparison(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_analyst),
    db: Session = Depends(get_db),
) -> SourceComparisonResponse:
    """Per-source observation count and averages, aggregated in SQL."""
    filters = _observation_filters(None, start_date, end_date)

    rows = db.execute(
        select(
            WeatherObservation.source,
            func.count(WeatherObservation.id),
            func.avg(WeatherObservation.temperature),
            func.sum(WeatherObservation.rainfall),
            func.avg(WeatherObservation.humidity),
            func.avg(WeatherObservation.wind_speed),
        )
        .where(and_(*filters) if filters else True)
        .group_by(WeatherObservation.source)
        .order_by(WeatherObservation.source)
    ).all()

    sources = [
        SourceComparisonItem(
            source=row[0],
            observation_count=row[1],
            average_temperature=round(row[2], 2) if row[2] is not None else None,
            rainfall=round(row[3], 2) if row[3] is not None else None,
            average_humidity=round(row[4], 2) if row[4] is not None else None,
            average_wind_speed=round(row[5], 2) if row[5] is not None else None,
        )
        for row in rows
    ]

    return SourceComparisonResponse(sources=sources)


@router.get("/anomalies", response_model=AnomalyAnalyticsResponse)
def get_anomaly_analytics(
    source: Optional[str] = Query(None),
    variable: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    latest_limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(require_analyst),
    db: Session = Depends(get_db),
) -> AnomalyAnalyticsResponse:
    """Anomaly counts by variable/severity plus the most recent flagged
    anomalies, aggregated in SQL. Every row in weather_anomalies is already
    a flagged anomaly (see ingest_analytics_data.py) - no additional
    thresholding happens here.
    """
    filters = []
    if source:
        filters.append(WeatherAnomaly.source == source)
    if variable:
        filters.append(WeatherAnomaly.variable == variable)
    if severity:
        filters.append(WeatherAnomaly.severity == severity.upper())
    if start_date:
        filters.append(WeatherAnomaly.observed_at >= start_date)
    if end_date:
        filters.append(WeatherAnomaly.observed_at <= end_date)
    where_clause = and_(*filters) if filters else True

    total = db.execute(select(func.count(WeatherAnomaly.id)).where(where_clause)).scalar_one()

    by_var_sev_rows = db.execute(
        select(WeatherAnomaly.variable, WeatherAnomaly.severity, func.count(WeatherAnomaly.id))
        .where(where_clause)
        .group_by(WeatherAnomaly.variable, WeatherAnomaly.severity)
        .order_by(WeatherAnomaly.variable, WeatherAnomaly.severity)
    ).all()

    by_severity_rows = db.execute(
        select(WeatherAnomaly.severity, func.count(WeatherAnomaly.id))
        .where(where_clause)
        .group_by(WeatherAnomaly.severity)
        .order_by(WeatherAnomaly.severity)
    ).all()

    latest_rows = db.execute(
        select(WeatherAnomaly)
        .where(where_clause)
        .order_by(WeatherAnomaly.observed_at.desc())
        .limit(latest_limit)
    ).scalars().all()

    return AnomalyAnalyticsResponse(
        total_anomalies=total or 0,
        by_variable_severity=[
            AnomalyVariableSeverityCount(variable=row[0], severity=row[1], count=row[2])
            for row in by_var_sev_rows
        ],
        by_severity=[AnomalySeverityCount(severity=row[0], count=row[1]) for row in by_severity_rows],
        latest=[AnomalyItem.model_validate(a) for a in latest_rows],
    )


@router.get("/event-distribution", response_model=EventDistributionResponse)
def get_event_distribution(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    city: Optional[str] = Query(None),
    current_user: dict = Depends(require_analyst),
    db: Session = Depends(get_db),
) -> EventDistributionResponse:
    """Real WeatherEvent category/severity distribution, aggregated in SQL."""
    filters = []
    if start_date:
        filters.append(WeatherEvent.start_time >= start_date)
    if end_date:
        filters.append(WeatherEvent.start_time <= end_date)
    if city:
        filters.append(WeatherEvent.location_name.like(f"%{city}%"))
    where_clause = and_(*filters) if filters else True

    total = db.execute(select(func.count(WeatherEvent.event_id)).where(where_clause)).scalar_one()

    by_type_rows = db.execute(
        select(WeatherEvent.event_type, func.count(WeatherEvent.event_id))
        .where(where_clause)
        .group_by(WeatherEvent.event_type)
        .order_by(func.count(WeatherEvent.event_id).desc())
    ).all()

    by_severity_rows = db.execute(
        select(WeatherEvent.severity, func.count(WeatherEvent.event_id))
        .where(where_clause)
        .group_by(WeatherEvent.severity)
        .order_by(WeatherEvent.severity)
    ).all()

    return EventDistributionResponse(
        total_events=total or 0,
        by_event_type=[EventTypeCount(event_type=row[0] or "UNKNOWN", count=row[1]) for row in by_type_rows],
        by_severity=[EventSeverityCount(severity=row[0] or "UNKNOWN", count=row[1]) for row in by_severity_rows],
    )


@router.get("/verification", response_model=VerificationAnalyticsResponse)
def get_verification_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_analyst),
    db: Session = Depends(get_db),
) -> VerificationAnalyticsResponse:
    """VERIFIED / NEEDS_REVIEW / REJECTED counts (final_verification_status),
    aggregated in SQL. Kept separate from evidence_status by design (see
    weather_events.evidence_status vs .final_verification_status).
    """
    filters = []
    if start_date:
        filters.append(WeatherEvent.start_time >= start_date)
    if end_date:
        filters.append(WeatherEvent.start_time <= end_date)
    where_clause = and_(*filters) if filters else True

    row = db.execute(
        select(
            func.count(WeatherEvent.event_id),
            func.count(WeatherEvent.event_id).filter(WeatherEvent.final_verification_status == "VERIFIED"),
            func.count(WeatherEvent.event_id).filter(WeatherEvent.final_verification_status == "NEEDS_REVIEW"),
            func.count(WeatherEvent.event_id).filter(WeatherEvent.final_verification_status == "REJECTED"),
        ).where(where_clause)
    ).one()
    total, verified, needs_review, rejected = row

    return VerificationAnalyticsResponse(
        total_events=total or 0,
        verified=verified or 0,
        needs_review=needs_review or 0,
        rejected=rejected or 0,
    )
