"""
Phase 5 Unit Tests

Tests for Phase 5 components that don't require a database:
- Schema validation
- Authentication
- Imports and pipeline integration

Run with: pytest backend/tests/test_phase5_unit.py -v
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

# Setup paths
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import pytest

# Test imports of Phase 1-4C
try:
    from src.schemas.weather_report import WeatherReport, EVENT_TYPES, VERIFICATION_STATUSES, SOURCE_TYPES
    from src.ingestion.report_normalizer import normalize_report
    from src.ingestion.report_dedup import detect_duplicates
    from src.ingestion.report_validators import validate_report
except ImportError:
    # Fallback: try direct imports
    from schemas.weather_report import WeatherReport, EVENT_TYPES, VERIFICATION_STATUSES, SOURCE_TYPES
# Test imports of Phase 5
from api.schemas import (
    ReportSubmissionRequest,
    ReportSubmissionResponse,
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
)
from api.auth.jwt_handler import JWTHandler


class TestPhase1to4CImports:
    """Test that Phase 1-4C functions import and work correctly."""
    
    def test_import_weather_report_schema(self):
        """Test WeatherReport schema imports."""
        assert "RAINFALL" in EVENT_TYPES
        assert "FLOODING" in EVENT_TYPES
        assert "THUNDERSTORM" in EVENT_TYPES
        assert "HEATWAVE" in EVENT_TYPES
        assert len(EVENT_TYPES) > 4
    
    def test_import_verification_statuses(self):
        """Test verification status constants."""
        assert "UNVERIFIED" in VERIFICATION_STATUSES
        assert "VERIFIED" in VERIFICATION_STATUSES
        assert "REJECTED" in VERIFICATION_STATUSES
        assert "SUSPICIOUS" in VERIFICATION_STATUSES
    
    def test_import_source_types(self):
        """Test source type constants."""
        assert "CITIZEN_REPORT" in SOURCE_TYPES
        assert "SOCIAL_MEDIA" in SOURCE_TYPES
        assert "API" in SOURCE_TYPES
    
    def test_create_weather_report_from_phase1to4c(self):
        """Test creating a WeatherReport using Phase 1-4C schema."""
        report = WeatherReport(
            source_type="CITIZEN_REPORT",
            city="Jabalpur",
            state="Madhya Pradesh",
            latitude=23.1815,
            longitude=79.9864,
            timestamp="2026-01-01T12:00:00Z",
            text="Heavy rainfall reported",
            event_type="RAINFALL",
        )
        assert report.report_id is not None
        assert report.source_type == "CITIZEN_REPORT"
        assert report.verification_status == "UNVERIFIED"
    
    def test_validate_report_integration(self):
        """Test Phase 3A validation integration."""
        report = WeatherReport(
            source_type="CITIZEN_REPORT",
            city="Jabalpur",
            state="Madhya Pradesh",
            latitude=23.1815,
            longitude=79.9864,
            timestamp="2026-01-01T12:00:00Z",
            text="Heavy rainfall reported",
            event_type="RAINFALL",
        )
        validated = validate_report(report)
        assert validated.verification_status in VERIFICATION_STATUSES
    
    def test_normalize_report_integration(self):
        """Test Phase 3A normalization integration."""
        report = WeatherReport(
            source_type="CITIZEN_REPORT",
            city="Jabalpur",
            state="Madhya Pradesh",
            latitude=23.1815,
            longitude=79.9864,
            timestamp="2026-01-01T12:00:00Z",
            text="Heavy rainfall reported",
            event_type="RAINFALL",
            source_reliability=None,
        )
        report = validate_report(report)
        normalized = normalize_report(report)
        assert normalized.source_reliability is not None
        assert 0.0 <= normalized.source_reliability <= 1.0
    
    def test_deduplicate_integration(self):
        """Test Phase 3A deduplication integration."""
        report1 = WeatherReport(
            source_type="CITIZEN_REPORT",
            city="Jabalpur",
            latitude=23.1815,
            longitude=79.9864,
            timestamp="2026-01-01T12:00:00Z",
            text="Heavy rainfall",
            event_type="RAINFALL",
        )
        report2 = WeatherReport(
            source_type="CITIZEN_REPORT",
            city="Jabalpur",
            latitude=23.1815,
            longitude=79.9864,
            timestamp="2026-01-01T12:01:00Z",
            text="Heavy rainfall",  # Same text
            event_type="RAINFALL",
        )
        
        detect_duplicates([report1, report2])
        assert report1.is_duplicate is False
        assert report2.is_duplicate is True  # Should be marked as duplicate


class TestPhase5Schemas:
    """Test Phase 5 Pydantic schemas."""
    
    def test_report_submission_request_validation(self):
        """Test ReportSubmissionRequest validation."""
        req = ReportSubmissionRequest(
            text="Heavy rainfall in Jabalpur",
            city="Jabalpur",
            state="Madhya Pradesh",
            latitude=23.1815,
            longitude=79.9864,
            event_type="RAINFALL",
        )
        assert req.text == "Heavy rainfall in Jabalpur"
        assert req.city == "Jabalpur"
    
    def test_report_submission_request_rejects_short_text(self):
        """Test that short text is rejected."""
        with pytest.raises(ValueError):
            ReportSubmissionRequest(
                text="Hi",  # Too short (min 10 chars)
                city="Jabalpur",
                event_type="RAINFALL",
            )
    
    def test_report_submission_request_rejects_invalid_coords(self):
        """Test that invalid coordinates are rejected."""
        with pytest.raises(ValueError):
            ReportSubmissionRequest(
                text="Heavy rainfall",
                city="Jabalpur",
                latitude=999.0,  # Invalid
                longitude=79.9864,
                event_type="RAINFALL",
            )
    
    def test_user_register_request_validation(self):
        """Test user registration request validation."""
        # NOTE: "test.local" is an RFC 6762 special-use domain and is
        # correctly rejected by email-validator (no network/DNS involved,
        # this is pure syntax). Use a domain that isn't reserved.
        req = UserRegisterRequest(
            email="user@example.com",
            password="SecurePassword123!",
            role="CITIZEN",
        )
        assert req.email == "user@example.com"
        assert req.role == "CITIZEN"
    
    def test_user_register_rejects_short_password(self):
        """Test that short password is rejected."""
        with pytest.raises(ValueError):
            UserRegisterRequest(
                email="user@example.com",
                password="short",  # Too short (min 8)
                role="CITIZEN",
            )


class TestJWTHandler:
    """Test JWT authentication handler."""
    
    def test_password_hashing(self):
        """Test password hashing."""
        plain_password = "MySecurePassword123!"
        hashed = JWTHandler.hash_password(plain_password)
        assert hashed != plain_password
        assert JWTHandler.verify_password(plain_password, hashed)
    
    def test_password_verification_fails_with_wrong_password(self):
        """Test that wrong password fails verification."""
        hashed = JWTHandler.hash_password("CorrectPassword123!")
        assert not JWTHandler.verify_password("WrongPassword123!", hashed)
    
    def test_create_access_token(self):
        """Test access token creation."""
        data = {
            "sub": str(uuid4()),
            "email": "user@test.local",
            "role": "CITIZEN",
        }
        token = JWTHandler.create_access_token(data)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 10
    
    def test_verify_token(self):
        """Test token verification."""
        data = {
            "sub": str(uuid4()),
            "email": "user@test.local",
            "role": "CITIZEN",
        }
        token = JWTHandler.create_access_token(data)
        verified = JWTHandler.verify_token(token)
        assert verified is not None
        assert verified["sub"] == data["sub"]
        assert verified["email"] == data["email"]
    
    def test_verify_invalid_token(self):
        """Test that invalid token fails verification."""
        verified = JWTHandler.verify_token("invalid.token.string")
        assert verified is None
    
    def test_extract_user_id_from_token(self):
        """Test extracting user ID from token."""
        user_id = str(uuid4())
        data = {
            "sub": user_id,
            "email": "user@test.local",
            "role": "CITIZEN",
        }
        token = JWTHandler.create_access_token(data)
        extracted_id = JWTHandler.extract_user_id_from_token(token)
        assert extracted_id == user_id
    
    def test_extract_role_from_token(self):
        """Test extracting role from token."""
        data = {
            "sub": str(uuid4()),
            "email": "user@test.local",
            "role": "ANALYST",
        }
        token = JWTHandler.create_access_token(data)
        extracted_role = JWTHandler.extract_role_from_token(token)
        assert extracted_role == "ANALYST"


class TestDataFlow:
    """Test the expected data flow through Phase 5."""
    
    def test_citizen_report_through_phase3a_pipeline(self):
        """Test a citizen report through Phase 3A pipeline."""
        # Citizen submits report via form
        submission = ReportSubmissionRequest(
            text="Heavy waterlogging near MG Road, Jabalpur",
            city="Jabalpur",
            state="Madhya Pradesh",
            latitude=23.1815,
            longitude=79.9864,
            event_type="FLOODING",
        )
        
        # Convert to Phase 1-4C schema
        phase3a_report = WeatherReport(
            source_type="CITIZEN_REPORT",
            timestamp=datetime.now(timezone.utc).isoformat(),
            city=submission.city,
            state=submission.state,
            latitude=submission.latitude,
            longitude=submission.longitude,
            text=submission.text,
            event_type=submission.event_type,
        )
        
        # Run through Phase 3A pipeline
        phase3a_report = validate_report(phase3a_report)
        assert phase3a_report.verification_status in VERIFICATION_STATUSES
        
        phase3a_report = normalize_report(phase3a_report)
        assert phase3a_report.source_reliability is not None
        
        detect_duplicates([phase3a_report])
        # Should not be marked as duplicate (first report)
        assert phase3a_report.is_duplicate is False
    
    def test_multiple_reports_deduplication(self):
        """Test deduplication of multiple reports."""
        # Create 3 reports within the SAME 30-minute time bucket.
        # NOTE: Phase 3A's detect_duplicates() is a documented, deliberate
        # baseline (src/ingestion/report_dedup.py) that buckets timestamps
        # into 30-minute windows. Reports spaced 1 hour apart (the original
        # version of this test) fall into DIFFERENT buckets and are
        # correctly NOT flagged as duplicates by that existing Phase 1-4C
        # logic. This was a bug in the test's fixture data, not in the
        # dedup code, and Phase 1-4C source is intentionally left untouched.
        reports = []
        for i in range(3):
            report = WeatherReport(
                source_type="CITIZEN_REPORT",
                timestamp=f"2026-01-01T12:{5*i:02d}:00Z",
                city="Jabalpur",
                latitude=23.1815,
                longitude=79.9864,
                text="Heavy rainfall near MG Road",
                event_type="RAINFALL",
            )
            report = validate_report(report)
            report = normalize_report(report)
            reports.append(report)
        
        # Detect duplicates
        detect_duplicates(reports)
        
        # First should not be duplicate, others should be
        assert reports[0].is_duplicate is False
        assert reports[1].is_duplicate is True
        assert reports[2].is_duplicate is True
        
        # All should have same duplicate group and hash
        assert reports[0].duplicate_hash == reports[1].duplicate_hash
        assert reports[0].duplicate_group_id == reports[1].duplicate_group_id


class TestPhase5Configuration:
    """Test Phase 5 configuration and environment."""
    
    def test_pydantic_schema_imports(self):
        """Test that all Pydantic schemas are importable."""
        from api.schemas import (
            ReportStatusResponse,
            EventResponse,
            EventListResponse,
            AdminReviewRequest,
            AlertResponse,
        )
        assert ReportStatusResponse is not None
        assert EventResponse is not None
        assert EventListResponse is not None
    
    def test_db_config_imports(self):
        """Test that database configuration imports work."""
        from api.config import get_settings
        settings = get_settings()
        assert settings is not None
    
    def test_auth_rbac_imports(self):
        """Test that RBAC imports work."""
        from api.auth.rbac import require_citizen, require_analyst, require_admin
        assert require_citizen is not None
        assert require_analyst is not None
        assert require_admin is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

