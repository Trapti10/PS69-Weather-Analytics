"""
PS69 Weather Analytics - Phase 5: Pydantic Schemas
Request/response validation and serialization
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# ============================================================================
# AUTHENTICATION SCHEMAS
# ============================================================================

class UserRegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    role: str = Field(default="CITIZEN", pattern="^CITIZEN$", description="Public registration creates citizen accounts only")


class UserLoginRequest(BaseModel):
    """User login request.

    ``role`` is optional for backwards compatibility with existing API clients,
    but the frontend login flow sends it so the server can verify that the
    selected login type matches the account's actual database role.
    """
    email: EmailStr
    password: str
    role: Optional[str] = Field(
        None,
        pattern="^(CITIZEN|ANALYST|ADMIN)$",
        description="Selected login type; when provided it must match the account's actual role",
    )


class TokenResponse(BaseModel):
    """Authentication token response."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user_id: UUID
    role: str
    expires_in: int


class UserResponse(BaseModel):
    """User information response."""
    user_id: UUID
    email: str
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============================================================================
# REPORT SCHEMAS
# ============================================================================

class ReportSubmissionRequest(BaseModel):
    """Citizen report submission."""
    text: str = Field(..., min_length=10, max_length=5000, description="Report text")
    city: str = Field(..., max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    event_type: str = Field(default="OTHER", max_length=50)
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    location_name: Optional[str] = None
    
    @validator("latitude", "longitude")
    def coordinates_both_or_none(cls, v, values):
        if "latitude" in values and values["latitude"] is not None:
            if v is None:
                raise ValueError("If latitude is provided, longitude must also be provided")
        return v


class ReportSubmissionResponse(BaseModel):
    """Citizen report submission response."""
    report_id: UUID
    event_id: Optional[UUID] = None
    evidence_status: Optional[str] = None
    evidence_support_score: Optional[float] = None
    verification_status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ReportStatusResponse(BaseModel):
    """Report status query response."""
    report_id: UUID
    source_type: str
    text: str
    city: str
    state: Optional[str]
    event_type: str
    verification_status: str
    evidence_status: Optional[str]
    evidence_support_score: Optional[float]
    final_verification_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    event_id: Optional[UUID] = None
    
    class Config:
        from_attributes = True


# ============================================================================
# PHASE 7: MY REPORTS LIST SCHEMA
# Additive only. Reuses ReportStatusResponse per-item instead of duplicating
# its fields. Backing endpoint: GET /reports/me (see routes/reports.py).
# ============================================================================

class ReportListResponse(BaseModel):
    """Paginated list of the authenticated user's own submitted reports."""
    reports: List[ReportStatusResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# EVENT SCHEMAS
# ============================================================================

class EventBase(BaseModel):
    """Base event information."""
    event_type: str
    location_name: str
    severity: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|EXTREME)$")
    start_time: datetime


class SourceVerdict(BaseModel):
    """Evidence source verdict from Phase 3C."""
    source_type: str
    source_name: str
    source_reliability: float
    agreement_status: str  # SUPPORTING, CONFLICTING, NEUTRAL, NO_DATA
    evidence_value: float
    reason: str


class EventResponse(BaseModel):
    """Event detail response."""
    event_id: UUID
    event_type: str
    location_name: str
    severity: str
    start_time: datetime
    end_time: Optional[datetime] = None

    # Phase 7 addition: surfaces the PostGIS point already stored on
    # WeatherEvent.location so the frontend map can plot real coordinates
    # instead of geocoding location_name. Null when a report was submitted
    # without coordinates. No schema/column change — this is read from the
    # existing geometry column via ST_X/ST_Y in routes/events.py.
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Evidence Status (Phase 3C)
    evidence_status: str  # SUPPORTED, CONFLICTING, UNVERIFIED, INSUFFICIENT_EVIDENCE
    evidence_support_score: Optional[float]
    evidence_detail: Optional[Dict[str, Any]] = None  # SourceVerdict list
    
    # Final Verification Status (Admin)
    final_verification_status: str
    
    # Member reports
    report_count: int
    unique_sources: int
    member_report_ids: List[UUID]
    
    # Admin review trail
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """Paginated event list response."""
    events: List[EventResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# ADMIN SCHEMAS
# ============================================================================

class AdminReviewRequest(BaseModel):
    """Admin review/verification request."""
    action: str = Field(..., pattern="^(VERIFIED|NEEDS_REVIEW|REJECTED)$")
    notes: Optional[str] = Field(None, max_length=2000)


class AdminReviewActionResponse(BaseModel):
    """Admin review action response."""
    action_id: UUID
    event_id: UUID
    admin_id: UUID
    action: str
    notes: Optional[str]
    evidence_summary: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True


class AdminQueueItemResponse(BaseModel):
    """Item in admin verification queue."""
    event_id: UUID
    event_type: str
    location_name: str
    severity: str
    evidence_status: str
    evidence_support_score: Optional[float]
    report_count: int
    created_at: datetime
    start_time: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# ALERT SCHEMAS
# ============================================================================

class AlertResponse(BaseModel):
    """Alert information."""
    alert_id: UUID
    event_id: UUID
    severity_threshold: str
    alert_status: str
    channel: str
    message: str
    triggered_at: datetime
    sent_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============================================================================
# PHASE 6: ADMIN VERIFICATION WORKFLOW SCHEMAS
# Additive only — nothing above this section is modified.
# Reuses AdminReviewRequest / AdminReviewActionResponse / AdminQueueItemResponse
# already defined above under "ADMIN SCHEMAS" instead of duplicating them.
# ============================================================================

class AdminQueueEntry(BaseModel):
    """One row in the admin verification queue."""
    event_id: UUID
    event_type: str
    location_name: str
    severity: str
    start_time: datetime
    evidence_status: str
    evidence_support_score: Optional[float] = None
    final_verification_status: str
    report_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AdminQueueResponse(BaseModel):
    """Paginated admin verification queue."""
    items: List[AdminQueueEntry]
    total: int
    limit: int
    offset: int


class EvidenceReportItem(BaseModel):
    """A single member report shown in the evidence detail view."""
    report_id: UUID
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    author_id_or_hash: Optional[str] = None
    report_timestamp: Optional[datetime] = None
    city: Optional[str] = None
    state: Optional[str] = None
    text: Optional[str] = None
    event_type: Optional[str] = None
    verification_status: Optional[str] = None
    source_reliability: Optional[float] = None
    predicted_event_category: Optional[str] = None
    event_classification_confidence: Optional[float] = None
    risk_score: Optional[float] = None
    risk_label: Optional[str] = None
    semantic_similarity_score: Optional[float] = None
    is_duplicate: bool = False
    is_suspicious: bool = False

    class Config:
        from_attributes = True


class EvidenceEventSummary(BaseModel):
    """Event-level summary shown at the top of the evidence detail view."""
    event_id: UUID
    event_type: str
    location_name: str
    severity: str
    start_time: datetime
    end_time: Optional[datetime] = None
    evidence_status: str
    evidence_support_score: Optional[float] = None
    final_verification_status: str
    report_count: int
    unique_sources: int

    class Config:
        from_attributes = True


class EvidenceDetailResponse(BaseModel):
    """
    Full evidence package for an event: the event summary, the Phase 3C
    external-source evidence (ERA5/IMD/Open-Meteo agreement, passed through
    from WeatherEvent.evidence_detail as-is), and the member reports.
    """
    event: EvidenceEventSummary
    external_evidence: Optional[Dict[str, Any]] = None
    reports: List[EvidenceReportItem]


class AdminVerifyResponse(BaseModel):
    """Response returned after an admin submits a final verification decision."""
    success: bool = True
    event_id: UUID
    previous_status: str
    final_verification_status: str
    reviewed_by: UUID
    reviewed_at: datetime
    notes: Optional[str] = None


# ============================================================================
# ANALYTICS SCHEMAS (database-backed weather intelligence dashboards)
# Additive only. Backed by weather_observations / weather_anomalies
# (real ERA5 + Open-Meteo + Phase 4C data, see backend/db/ingest_analytics_data.py)
# and the existing weather_events / weather_reports tables. All aggregation
# happens in SQL (routes/analytics.py) - these schemas only shape the
# already-aggregated response.
# ============================================================================

class AnalyticsOverviewResponse(BaseModel):
    """Top-line KPIs for the Analyst/Admin intelligence dashboard."""
    total_weather_observations: int
    total_weather_events: int
    total_reports: int
    total_anomalies: int
    total_sources: int
    verified_events: int
    needs_review: int
    rejected_events: int
    average_temperature: Optional[float] = None
    max_temperature: Optional[float] = None
    total_rainfall: Optional[float] = None
    measurements_analyzed: Optional[int] = None
    anomaly_rate: Optional[float] = None
    observations_date_range_start: Optional[datetime] = None
    observations_date_range_end: Optional[datetime] = None


class DataQualitySourceSummary(BaseModel):
    source: str
    input_records: int
    records_without_timestamp: int
    duplicate_timestamps_dropped: int
    invalid_rainfall_count: int


class DataQualityAnalyticsResponse(BaseModel):
    total_observations_analyzed: int
    evaluated_observations: int
    insufficient_history_count: int
    missing_value_count: int
    invalid_value_count: int
    zero_variance_count: int
    variables_analyzed: int
    by_source: List[DataQualitySourceSummary]


class WeatherTrendPoint(BaseModel):
    """One time bucket of aggregated weather_observations."""
    date: str  # ISO date (day-bucketed)
    average_temperature: Optional[float] = None
    rainfall: Optional[float] = None
    average_humidity: Optional[float] = None
    average_wind_speed: Optional[float] = None
    average_pressure: Optional[float] = None
    observation_count: int


class WeatherTrendsResponse(BaseModel):
    trends: List[WeatherTrendPoint]
    source: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class RainfallTrendPoint(BaseModel):
    date: str
    total_rainfall: Optional[float] = None
    observation_count: int


class RainfallAnalyticsResponse(BaseModel):
    trends: List[RainfallTrendPoint]
    total_rainfall: Optional[float] = None
    max_daily_rainfall: Optional[float] = None


class TemperatureTrendPoint(BaseModel):
    date: str
    average_temperature: Optional[float] = None
    min_temperature: Optional[float] = None
    max_temperature: Optional[float] = None
    observation_count: int


class TemperatureAnalyticsResponse(BaseModel):
    trends: List[TemperatureTrendPoint]
    average_temperature: Optional[float] = None
    min_temperature: Optional[float] = None
    max_temperature: Optional[float] = None


class SourceComparisonItem(BaseModel):
    source: str
    observation_count: int
    average_temperature: Optional[float] = None
    rainfall: Optional[float] = None
    average_humidity: Optional[float] = None
    average_wind_speed: Optional[float] = None


class SourceComparisonResponse(BaseModel):
    sources: List[SourceComparisonItem]


class AnomalyVariableSeverityCount(BaseModel):
    variable: str
    severity: str
    count: int


class AnomalySeverityCount(BaseModel):
    severity: str
    count: int


class AnomalyItem(BaseModel):
    """A single flagged anomaly, for the 'latest anomalies' feed."""
    id: UUID
    source: str
    observed_at: datetime
    variable: str
    observed_value: Optional[float] = None
    baseline_value: Optional[float] = None
    severity: str
    explanation: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None

    class Config:
        from_attributes = True


class AnomalyMonthCount(BaseModel):
    month: str
    count: int


class AnomalySourceCount(BaseModel):
    source: str
    count: int


class AnomalyVariableCount(BaseModel):
    variable: str
    count: int


class AnomalyAnalyticsResponse(BaseModel):
    total_anomalies: int
    by_variable_severity: List[AnomalyVariableSeverityCount]
    by_severity: List[AnomalySeverityCount]
    by_month: List[AnomalyMonthCount] = []
    by_source: List[AnomalySourceCount] = []
    by_variable: List[AnomalyVariableCount] = []
    latest: List[AnomalyItem]


class EventTypeCount(BaseModel):
    event_type: str
    count: int


class EventSeverityCount(BaseModel):
    severity: str
    count: int


class EventDistributionResponse(BaseModel):
    total_events: int
    by_event_type: List[EventTypeCount]
    by_severity: List[EventSeverityCount]


class VerificationAnalyticsResponse(BaseModel):
    total_events: int
    verified: int
    needs_review: int
    rejected: int


# ============================================================================
# ERROR SCHEMAS
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ============================================================================
# RESEARCH / INTELLIGENCE ARTIFACT SCHEMAS
# ============================================================================

class FusionAnalyticsResponse(BaseModel):
    era5_records: int
    openmeteo_records: int
    matched_temporal: int
    matched_temporal_spatial: int
    not_matched: int
    grid_distance_km: Optional[float] = None
    confidence_count: int
    confidence_mean: Optional[float] = None
    confidence_min: Optional[float] = None
    confidence_max: Optional[float] = None
    agreement_by_variable: List[Dict[str, Any]]
    scientific_note: Optional[str] = None


class CorroborationAnalyticsResponse(BaseModel):
    total_reports: int
    supported: int
    conflicting: int
    unverified: int
    insufficient_evidence: int
    average_evidence_support_score: Optional[float] = None
    reports_with_a_score: int
    evidence_source_usage: List[Dict[str, Any]]
    honest_note: Optional[str] = None


class IntelligenceAnalyticsResponse(BaseModel):
    total_intelligence_records: int
    matched_sources: int
    source_agreement_mean: Optional[float] = None
    supported_reports: int
    unverified_reports: int
    conflicting_reports: int
    average_evidence_support_score: Optional[float] = None
    average_overall_confidence: Optional[float] = None
    confidence_bands: List[Dict[str, Any]]
    corroboration_counts: List[Dict[str, Any]]
    latest_signals: List[Dict[str, Any]]
    scientific_note: Optional[str] = None


class ModelPerformanceRow(BaseModel):
    model: str
    target: str
    horizon_h: int
    mae: Optional[float] = None
    rmse: Optional[float] = None
    r2: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    roc_auc: Optional[float] = None
    train_samples: Optional[int] = None
    test_samples: Optional[int] = None


class ModelPerformanceResponse(BaseModel):
    horizons: List[int]
    temperature: List[ModelPerformanceRow]
    rainfall: List[ModelPerformanceRow]
    headline: Dict[str, Any]


class ResearchArtifact(BaseModel):
    artifact_id: str
    name: str
    category: str
    format: str
    size_bytes: int
    row_count: Optional[int] = None
    description: str
    source_path: str
    download_endpoint: str


class ResearchArtifactListResponse(BaseModel):
    artifacts: List[ResearchArtifact]


class ResearchArtifactPreviewResponse(BaseModel):
    artifact: ResearchArtifact
    columns: List[str]
    rows: List[Any]


class LocationSearchItem(BaseModel):
    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observation_count: int = 0
    anomaly_count: int = 0
    event_count: int = 0
    coverage_start: Optional[datetime] = None
    coverage_end: Optional[datetime] = None


class LocationSearchResponse(BaseModel):
    locations: List[LocationSearchItem]


class PublicLocationEvent(BaseModel):
    event_id: UUID
    event_type: str
    location_name: str
    severity: str
    start_time: datetime
    end_time: Optional[datetime] = None
    final_verification_status: str


class PublicLocationSummaryResponse(BaseModel):
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    dataset_coverage_start: Optional[datetime] = None
    dataset_coverage_end: Optional[datetime] = None
    observation_count: int = 0
    anomaly_count: int = 0
    events: List[PublicLocationEvent]
    note: Optional[str] = None
