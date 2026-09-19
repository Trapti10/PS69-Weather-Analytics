"""
PS69 Weather Analytics - Analytics Routes

Database-backed weather intelligence for the Analyst/Admin dashboards.

Every endpoint here does its aggregation in PostgreSQL (COUNT/AVG/SUM/MIN/MAX/
GROUP BY/date_trunc) and returns already-aggregated JSON - none of this loads
raw observation rows into Python for calculation, and none of it is ever sent
to the frontend as raw rows for client-side math.

Data sources:
- weather_observations / weather_anomalies: real ERA5 + Open-Meteo +
  anomaly data, populated by backend/db/ingest_analytics_data.py
  (see backend/db/schema.sql for provenance comments on both tables).
- weather_events: the existing citizen-report/verification pipeline
  (event/verification pipeline, unchanged by this file.

Authorization: ANALYST and ADMIN only (require_analyst already allows both).
Citizen-facing analytics are intentionally NOT exposed here - the Citizen
dashboard consumes /reports and /events directly, not this router.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, case

from backend.api.db import get_db
from backend.api.auth.rbac import require_analyst
from backend.api.models import WeatherObservation, WeatherAnomaly, WeatherEvent, WeatherReport
from backend.api.schemas import (
    AnalyticsOverviewResponse,
    DataQualityAnalyticsResponse,
    DataQualitySourceSummary,
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
    AnomalyMonthCount,
    AnomalySourceCount,
    AnomalyVariableCount,
    AnomalyItem,
    EventDistributionResponse,
    EventTypeCount,
    EventSeverityCount,
    VerificationAnalyticsResponse,
    FusionAnalyticsResponse,
    CorroborationAnalyticsResponse,
    IntelligenceAnalyticsResponse,
    ModelPerformanceRow,
    ModelPerformanceResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parents[3]
METRICS_PATH = REPO_ROOT / "data" / "phase4b" / "metrics.json"


def _load_json_file(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        logger.warning("Unable to read analytical metadata file: %s", path)
        return {}


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
    source: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_analyst),
    db: Session = Depends(get_db),
) -> AnalyticsOverviewResponse:
    """Top-line KPIs combining weather intelligence with the event pipeline.
    Optional source/date filters are applied server-side and all aggregation
    remains in SQL.
    """
    observation_where = _observation_filters(source, start_date, end_date)
    observation_clause = and_(*observation_where) if observation_where else True
    measurement_count = (
        case((WeatherObservation.temperature.is_not(None), 1), else_=0)
        + case((WeatherObservation.rainfall.is_not(None), 1), else_=0)
        + case((WeatherObservation.wind_speed.is_not(None), 1), else_=0)
        + case((WeatherObservation.pressure.is_not(None), 1), else_=0)
    )
    obs_row = db.execute(
        select(
            func.count(WeatherObservation.id),
            func.count(func.distinct(WeatherObservation.source)),
            func.avg(WeatherObservation.temperature),
            func.max(WeatherObservation.temperature),
            func.sum(WeatherObservation.rainfall),
            func.min(WeatherObservation.observed_at),
            func.max(WeatherObservation.observed_at),
            func.sum(measurement_count),
        ).where(observation_clause)
    ).one()
    (
        total_observations,
        total_sources,
        avg_temp,
        max_temp,
        total_rainfall,
        obs_start,
        obs_end,
        measurements_analyzed,
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
        measurements_analyzed=int(measurements_analyzed or 0),
        anomaly_rate=(float(total_anomalies) / float(measurements_analyzed)) if measurements_analyzed else 0.0,
        observations_date_range_start=obs_start,
        observations_date_range_end=obs_end,
    )


@router.get("/data-quality", response_model=DataQualityAnalyticsResponse)
def get_data_quality_analytics(
    current_user: dict = Depends(require_analyst),
) -> DataQualityAnalyticsResponse:
    """Expose the persisted preparation/quality summary used by the anomaly pipeline.

    This is metadata, not a raw-row dump: the large source datasets remain in
    PostgreSQL and the Research Data catalog.
    """
    summary = _load_json_file(REPO_ROOT / "data" / "phase4c" / "anomaly_summary.json")
    status_counts = summary.get("status_counts") or {}
    prep = summary.get("prep_summary_by_source") or {}
    by_source = [
        DataQualitySourceSummary(
            source=source,
            input_records=int(item.get("input_records") or 0),
            records_without_timestamp=int(item.get("records_without_timestamp") or 0),
            duplicate_timestamps_dropped=int(item.get("duplicate_timestamps_dropped") or 0),
            invalid_rainfall_count=int(item.get("invalid_rainfall_count") or 0),
        )
        for source, item in prep.items()
    ]
    return DataQualityAnalyticsResponse(
        total_observations_analyzed=int(summary.get("total_observations_analyzed") or 0),
        evaluated_observations=int(status_counts.get("EVALUATED") or 0),
        insufficient_history_count=int(summary.get("insufficient_history_count") or 0),
        missing_value_count=int(summary.get("missing_value_count") or 0),
        invalid_value_count=int(summary.get("invalid_value_count") or 0),
        zero_variance_count=int(summary.get("zero_variance_count") or 0),
        variables_analyzed=4,
        by_source=by_source,
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

    month = func.date_trunc("month", WeatherAnomaly.observed_at)
    by_month_rows = db.execute(
        select(month.label("month"), func.count(WeatherAnomaly.id))
        .where(where_clause)
        .group_by(month)
        .order_by(month)
    ).all()
    by_source_rows = db.execute(
        select(WeatherAnomaly.source, func.count(WeatherAnomaly.id))
        .where(where_clause)
        .group_by(WeatherAnomaly.source)
        .order_by(func.count(WeatherAnomaly.id).desc())
    ).all()
    by_variable_rows = db.execute(
        select(WeatherAnomaly.variable, func.count(WeatherAnomaly.id))
        .where(where_clause)
        .group_by(WeatherAnomaly.variable)
        .order_by(func.count(WeatherAnomaly.id).desc())
    ).all()

    return AnomalyAnalyticsResponse(
        total_anomalies=total or 0,
        by_variable_severity=[
            AnomalyVariableSeverityCount(variable=row[0], severity=row[1], count=row[2])
            for row in by_var_sev_rows
        ],
        by_severity=[AnomalySeverityCount(severity=row[0], count=row[1]) for row in by_severity_rows],
        by_month=[AnomalyMonthCount(month=row[0].strftime("%Y-%m"), count=row[1]) for row in by_month_rows],
        by_source=[AnomalySourceCount(source=row[0], count=row[1]) for row in by_source_rows],
        by_variable=[AnomalyVariableCount(variable=row[0], count=row[1]) for row in by_variable_rows],
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

# ---------------------------------------------------------------------------
# Extended intelligence endpoints. These read the project's small analytical
# artifacts for metrics that are not raw observation rows (fusion summary,
# corroboration summary, weather intelligence records and forecast/model metrics).
# The large observation/anomaly datasets remain database-backed above.
# ---------------------------------------------------------------------------

from functools import lru_cache
import csv


def _load_json(path: str):
    with (REPO_ROOT / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=8)
def _load_fusion_summary() -> dict:
    return _load_json("data/phase2c/fused/phase2c_summary.json")


@lru_cache(maxsize=8)
def _load_corroboration_summary() -> dict:
    return _load_json("data/phase3c/verification_summary.json")


@lru_cache(maxsize=8)
def _load_intelligence_records() -> list[dict]:
    return _load_json("data/phase4/weather_intelligence.json")


def _load_model_rows() -> list[dict]:
    with (REPO_ROOT / "data/phase4b/model_comparison.csv").open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


@router.get("/fusion", response_model=FusionAnalyticsResponse)
def get_fusion_analytics(
    current_user: dict = Depends(require_analyst),
) -> FusionAnalyticsResponse:
    summary = _load_fusion_summary()
    confidence = summary.get("confidence_score_stats") or {}
    return FusionAnalyticsResponse(
        era5_records=int(summary.get("n_era5_records") or 0),
        openmeteo_records=int(summary.get("n_openmeteo_records") or 0),
        matched_temporal=int(summary.get("n_pairs_with_matching_timestamp") or 0),
        matched_temporal_spatial=int(summary.get("n_matched_temporal_and_spatial") or 0),
        not_matched=int(summary.get("n_not_matched") or 0),
        grid_distance_km=summary.get("grid_distance_km"),
        confidence_count=int(confidence.get("n") or 0),
        confidence_mean=confidence.get("mean"),
        confidence_min=confidence.get("min"),
        confidence_max=confidence.get("max"),
        agreement_by_variable=[
            {"variable": variable, **counts}
            for variable, counts in (summary.get("variable_agreement_stats") or {}).items()
            if variable != "wind_gust_bonus"
        ],
        scientific_note=summary.get("scientific_note"),
    )


@router.get("/corroboration", response_model=CorroborationAnalyticsResponse)
def get_corroboration_analytics(
    current_user: dict = Depends(require_analyst),
) -> CorroborationAnalyticsResponse:
    summary = _load_corroboration_summary()
    counts = summary.get("verification_status_counts") or {}
    return CorroborationAnalyticsResponse(
        total_reports=int(summary.get("total_reports") or 0),
        supported=int(counts.get("SUPPORTED") or 0),
        conflicting=int(counts.get("CONFLICTING") or 0),
        unverified=int(counts.get("UNVERIFIED") or 0),
        insufficient_evidence=int(counts.get("INSUFFICIENT_EVIDENCE") or 0),
        average_evidence_support_score=summary.get("average_evidence_support_score"),
        reports_with_a_score=int(summary.get("reports_with_a_score") or 0),
        evidence_source_usage=[
            {"source": source, "count": count}
            for source, count in (summary.get("evidence_source_usage_counts") or {}).items()
        ],
        honest_note=summary.get("honest_note"),
    )


@router.get("/intelligence", response_model=IntelligenceAnalyticsResponse)
def get_intelligence_analytics(
    current_user: dict = Depends(require_analyst),
) -> IntelligenceAnalyticsResponse:
    records = _load_intelligence_records()
    if not records:
        return IntelligenceAnalyticsResponse(
            total_intelligence_records=0,
            matched_sources=0,
            supported_reports=0,
            unverified_reports=0,
            conflicting_reports=0,
            confidence_bands=[],
            corroboration_counts=[],
            latest_signals=[],
        )

    source_conf = [
        float(r["source_agreement_confidence"])
        for r in records
        if isinstance(r.get("source_agreement_confidence"), (int, float))
    ]
    evidence_scores = [
        float(r["evidence_support_score"])
        for r in records
        if isinstance(r.get("evidence_support_score"), (int, float))
    ]
    overall = [
        float(r["overall_confidence"])
        for r in records
        if isinstance(r.get("overall_confidence"), (int, float))
    ]

    matched = sum(1 for r in records if r.get("source_agreement_match_status") == "MATCHED")
    supported = sum(
        1 for r in records
        if r.get("corroboration_status") == "SUPPORTED"
    )
    unverified = sum(
        1 for r in records
        if r.get("corroboration_status") == "UNVERIFIED"
    )
    conflicting = sum(
        1 for r in records
        if r.get("corroboration_status") == "CONFLICTING"
    )

    bands = [
        ("HIGH (≥0.80)", lambda x: x >= 0.8),
        ("MEDIUM (0.60–0.79)", lambda x: 0.6 <= x < 0.8),
        ("LOW (<0.60)", lambda x: x < 0.6),
    ]
    confidence_bands = [
        {"band": label, "count": sum(1 for value in overall if predicate(value))}
        for label, predicate in bands
    ]

    corroboration_counts = [
        {"status": status, "count": sum(1 for r in records if r.get("corroboration_status") == status)}
        for status in ("SUPPORTED", "UNVERIFIED", "CONFLICTING")
    ]

    latest_signals = sorted(records, key=lambda x: x.get("timestamp") or "", reverse=True)[:8]
    return IntelligenceAnalyticsResponse(
        total_intelligence_records=len(records),
        matched_sources=matched,
        source_agreement_mean=round(sum(source_conf) / len(source_conf), 3) if source_conf else None,
        supported_reports=supported,
        unverified_reports=unverified,
        conflicting_reports=conflicting,
        average_evidence_support_score=round(sum(evidence_scores) / len(evidence_scores), 3) if evidence_scores else None,
        average_overall_confidence=round(sum(overall) / len(overall), 3) if overall else None,
        confidence_bands=confidence_bands,
        corroboration_counts=corroboration_counts,
        latest_signals=[
            {
                "timestamp": record.get("timestamp"),
                "latitude": record.get("latitude"),
                "longitude": record.get("longitude"),
                "sources": record.get("contributing_sources") or [],
                "source_agreement": record.get("source_agreement_match_status"),
                "confidence": record.get("overall_confidence"),
                "corroboration": record.get("corroboration_status"),
                "event_category": (record.get("report_evidence") or [{}])[0].get("event_category") if record.get("report_evidence") else None,
            }
            for record in latest_signals
        ],
        scientific_note=(records[0].get("confidence_method") if records else None),
    )


@router.get("/model-performance", response_model=ModelPerformanceResponse)
def get_model_performance(
    current_user: dict = Depends(require_analyst),
) -> ModelPerformanceResponse:
    rows = _load_model_rows()
    parsed = []
    for row in rows:
        def num(key: str):
            value = row.get(key)
            return float(value) if value not in (None, "") else None
        parsed.append(
            ModelPerformanceRow(
                model=row["Model"],
                target=row["Target"],
                horizon_h=int(row["Horizon_h"]),
                mae=num("MAE"),
                rmse=num("RMSE"),
                r2=num("R2"),
                precision=num("Precision"),
                recall=num("Recall"),
                f1=num("F1"),
                roc_auc=num("ROC_AUC"),
                train_samples=int(row["Train_samples"]) if row.get("Train_samples") else None,
                test_samples=int(row["Test_samples"]) if row.get("Test_samples") else None,
            )
        )

    temperature = [r for r in parsed if r.target == "temperature"]
    rainfall = [r for r in parsed if r.target == "rainfall"]
    metrics = _load_json_file(METRICS_PATH)
    temp_1h = [r for r in temperature if r.horizon_h == 1 and r.r2 is not None]
    rain_1h = [r for r in rainfall if r.horizon_h == 1 and r.roc_auc is not None]
    best_temp_1h = max(temp_1h, key=lambda r: r.r2 or float("-inf"), default=None)
    best_rain_1h = max(rain_1h, key=lambda r: r.roc_auc or float("-inf"), default=None)
    headline = {
        "temperature_1h_best_model": best_temp_1h.model if best_temp_1h else None,
        "temperature_1h_r2": best_temp_1h.r2 if best_temp_1h else None,
        "rainfall_1h_best_model": best_rain_1h.model if best_rain_1h else None,
        "rainfall_1h_roc_auc": best_rain_1h.roc_auc if best_rain_1h else None,
        "models_saved": metrics.get("n_models_saved", len(parsed)),
    }
    horizons = sorted({r.horizon_h for r in parsed})
    return ModelPerformanceResponse(
        horizons=horizons,
        temperature=temperature,
        rainfall=rainfall,
        headline=headline,
    )
