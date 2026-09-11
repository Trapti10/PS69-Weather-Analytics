"""
PS69 Weather Analytics - Phase 5: SQLAlchemy ORM Models
Maps to PostgreSQL schema (6 tables)
"""

from sqlalchemy import Column, String, Text, Float, Boolean, DateTime, ARRAY, UUID, ForeignKey, CheckConstraint, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime
import uuid

from api.db import Base


class User(Base):
    """User account (Citizen, Analyst, or Admin)."""
    __tablename__ = "users"
    
    user_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="CITIZEN", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("role IN ('CITIZEN', 'ANALYST', 'ADMIN')"),
    )
    
    # Relationships
    admin_review_actions = relationship("AdminReviewAction", back_populates="admin")
    audit_log_entries = relationship("AuditLog", back_populates="actor")


class WeatherReport(Base):
    """Weather report from any source (citizen, social, API, etc.)."""
    __tablename__ = "weather_reports"
    
    report_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    source_type = Column(String(50))  # SOCIAL_MEDIA, CITIZEN_REPORT, API, etc.
    source_name = Column(String(100))
    author_id_or_hash = Column(String(255))  # hashed
    report_timestamp = Column(DateTime)
    ingestion_timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    city = Column(String(100))
    state = Column(String(100))
    location = Column(Geometry("POINT", srid=4326), index=True)  # PostGIS point
    text = Column(Text)
    image_url = Column(String(500))
    video_url = Column(String(500))
    event_type = Column(String(50))  # RAINFALL, THUNDERSTORM, etc.
    raw_event_type = Column(String(100))
    verification_status = Column(String(20))  # UNVERIFIED, VERIFIED, REJECTED, SUSPICIOUS
    source_reliability = Column(Float)
    is_duplicate = Column(Boolean, default=False)
    duplicate_hash = Column(String(255), index=True)
    event_id = Column(UUID, ForeignKey("weather_events.event_id"), index=True, nullable=True)
    is_suspicious = Column(Boolean, default=False)
    
    # Phase 3B Intelligence
    semantic_similarity_score = Column(Float)
    predicted_event_category = Column(String(50))
    event_classification_confidence = Column(Float)
    risk_score = Column(Float)
    risk_label = Column(String(50))
    
    raw_payload = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    event = relationship("WeatherEvent", back_populates="member_reports")


class WeatherEvent(Base):
    """Weather event (groups related reports, carries evidence & verification status)."""
    __tablename__ = "weather_events"
    
    event_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50))  # RAINFALL, FLOODING, HEATWAVE, etc.
    location = Column(Geometry("POINT", srid=4326), index=True)  # PostGIS centroid
    location_name = Column(String(255))  # city / state / region
    start_time = Column(DateTime, index=True)
    end_time = Column(DateTime)
    severity = Column(String(20), default="MEDIUM", index=True)
    
    # Evidence Status (Phase 3C - FROZEN, never collapsed)
    evidence_status = Column(String(50), index=True)  # SUPPORTED, CONFLICTING, UNVERIFIED, INSUFFICIENT_EVIDENCE
    evidence_support_score = Column(Float)  # 0.0-1.0
    evidence_detail = Column(JSONB)  # SourceVerdict list and thresholds
    
    # Final Verification Status (Admin-only)
    final_verification_status = Column(String(20), default="NEEDS_REVIEW", index=True)  # VERIFIED, NEEDS_REVIEW, REJECTED
    
    # Member Reports
    member_report_ids = Column(ARRAY(UUID), default=list)
    report_count = Column(Integer, default=0)
    unique_sources = Column(Integer, default=0)
    
    # Admin Review Audit Trail
    reviewed_by = Column(UUID, ForeignKey("users.user_id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH', 'EXTREME')"),
        CheckConstraint("evidence_status IN ('SUPPORTED', 'CONFLICTING', 'UNVERIFIED', 'INSUFFICIENT_EVIDENCE')"),
        CheckConstraint("final_verification_status IN ('VERIFIED', 'NEEDS_REVIEW', 'REJECTED')"),
    )
    
    # Relationships
    member_reports = relationship("WeatherReport", back_populates="event")
    admin_review_actions = relationship("AdminReviewAction", back_populates="event", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="event", cascade="all, delete-orphan")
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by])


class AdminReviewAction(Base):
    """Admin decision audit log (immutable)."""
    __tablename__ = "admin_review_actions"
    
    action_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID, ForeignKey("weather_events.event_id"), nullable=False, index=True)
    admin_id = Column(UUID, ForeignKey("users.user_id"), nullable=False, index=True)
    action = Column(String(50))  # VERIFIED, NEEDS_REVIEW, REJECTED, NOTE_ADDED, STATUS_CHANGED
    notes = Column(Text)
    evidence_summary = Column(JSONB)  # JSON summary of reviewed evidence
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("action IN ('VERIFIED', 'NEEDS_REVIEW', 'REJECTED', 'NOTE_ADDED', 'STATUS_CHANGED')"),
    )
    
    # Relationships
    event = relationship("WeatherEvent", back_populates="admin_review_actions")
    admin = relationship("User", back_populates="admin_review_actions")


class Alert(Base):
    """Alert triggered by verified events."""
    __tablename__ = "alerts"
    
    alert_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID, ForeignKey("weather_events.event_id"), nullable=False, index=True)
    severity_threshold = Column(String(20))
    alert_status = Column(String(20), default="TRIGGERED", index=True)  # TRIGGERED, SENT, ACKNOWLEDGED, EXPIRED
    channel = Column(String(50))  # SMS, EMAIL, CONSOLE, WEBHOOK
    message = Column(Text)
    recipient_id = Column(UUID, ForeignKey("users.user_id"), nullable=True, index=True)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("alert_status IN ('TRIGGERED', 'SENT', 'ACKNOWLEDGED', 'EXPIRED')"),
    )
    
    # Relationships
    event = relationship("WeatherEvent", back_populates="alerts")
    recipient = relationship("User")


class AuditLog(Base):
    """Immutable audit trail of all changes."""
    __tablename__ = "audit_log"
    
    log_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), index=True)  # WEATHER_EVENT, WEATHER_REPORT, USER, ALERT
    entity_id = Column(UUID, index=True)
    action = Column(String(50), index=True)  # CREATE, UPDATE, DELETE, VERIFY, REJECT
    actor_id = Column(UUID, ForeignKey("users.user_id"), nullable=True)
    changes = Column(JSONB)  # JSON diff
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    actor = relationship("User", back_populates="audit_log_entries")

