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
    """User login request."""
    email: EmailStr
    password: str


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
# ERROR SCHEMAS
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

