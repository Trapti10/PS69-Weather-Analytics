"""
Phase 5 Integration Tests

Test the complete flow:
1. Register user
2. Login
3. Submit citizen report (synchronous processing)
4. Query report status
5. Query events
6. Event creation and correlation

Tests assume PostgreSQL + PostGIS is running on localhost:5432
"""

import sys
import os
import json
from pathlib import Path
from uuid import UUID

# Add src to path for Phase 1-4C imports
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import FastAPI app and models
from phase5.api.main import app
from phase5.api.db import Base, get_db
from phase5.api.models import User, WeatherReport, WeatherEvent, AuditLog
from phase5.api.auth.jwt_handler import JWTHandler


# Test database setup
# NOTE: password must match the credential used everywhere else in the
# project (docker-compose.yml, phase5/api/config.py, phase5/setup.sh):
# "ps69_password_dev", not "ps69_dev_password". The old value silently
# caused every test in this file to fail to connect and get skipped via
# the pytest.skip() in the test_db fixture below, instead of being run.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://ps69_admin:ps69_password_dev@localhost:5432/ps69_weather_test"
)

@pytest.fixture(scope="session")
def test_db():
    """Create the dedicated PostgreSQL test database and its tables.

    Database unavailability is a hard test failure, not a skip, because Phase 5
    acceptance requires real PostgreSQL/PostGIS integration tests to execute.
    """
    engine = None
    admin_engine = None
    try:
        # Create the test database when it does not exist.
        db_url = TEST_DATABASE_URL
        marker = "/ps69_weather_test"
        if marker in db_url:
            admin_url = db_url.replace(marker, "/postgres")
            admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", echo=False)
            with admin_engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = 'ps69_weather_test'")
                ).scalar()
                if not exists:
                    conn.execute(text("CREATE DATABASE ps69_weather_test"))

        engine = create_engine(TEST_DATABASE_URL, echo=False)

        # Extensions are enabled per database. The dedicated test database is
        # created from the PostgreSQL template, so explicitly enable PostGIS
        # before verifying it. This is safe to repeat.
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.commit()

        # Verify PostGIS before creating ORM tables.
        with engine.connect() as conn:
            conn.execute(text("SELECT postgis_version()"))
        Base.metadata.create_all(bind=engine)
        yield engine
    except Exception as e:
        pytest.fail(f"PostgreSQL/PostGIS test database is unavailable: {e}")
    finally:
        if engine is not None:
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
        if admin_engine is not None:
            admin_engine.dispose()


@pytest.fixture
def db_session(test_db):
    """Create a test session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    """Create test client with database override."""
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ============================================================================
# TESTS
# ============================================================================

class TestAuthentication:
    """Test JWT authentication flow."""
    
    def test_register_citizen(self, client):
        """Test user registration."""
        response = client.post(
            "/auth/register",
            json={
                "email": "citizen@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["role"] == "CITIZEN"
        assert "user_id" in data
    
    def test_register_duplicate_email(self, client):
        """Test duplicate registration fails."""
        # Register first user
        client.post(
            "/auth/register",
            json={
                "email": "duplicate@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        
        # Try to register again with same email
        response = client.post(
            "/auth/register",
            json={
                "email": "duplicate@test.com",
                "password": "TestPassword456!",
                "role": "CITIZEN",
            },
        )
        assert response.status_code == 400
    
    def test_login(self, client):
        """Test user login."""
        # Register
        client.post(
            "/auth/register",
            json={
                "email": "login@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        
        # Login
        response = client.post(
            "/auth/login",
            json={
                "email": "login@test.com",
                "password": "TestPassword123!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    def test_login_wrong_password(self, client):
        """Test login with wrong password fails."""
        # Register
        client.post(
            "/auth/register",
            json={
                "email": "wrongpw@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        
        # Try to login with wrong password
        response = client.post(
            "/auth/login",
            json={
                "email": "wrongpw@test.com",
                "password": "WrongPassword456!",
            },
        )
        assert response.status_code == 401


class TestReportSubmission:
    """Test citizen report submission (core MVP endpoint)."""
    
    def test_submit_report_requires_auth(self, client):
        """Test that unauthenticated requests are rejected."""
        response = client.post(
            "/reports/",
            json={
                "text": "Heavy rain in Jabalpur",
                "city": "Jabalpur",
                "state": "Madhya Pradesh",
                "latitude": 23.1815,
                "longitude": 79.9864,
                "event_type": "RAINFALL",
            },
        )
        assert response.status_code == 401
    
    def test_submit_report_success(self, client):
        """Test successful report submission."""
        # Register and login
        reg_response = client.post(
            "/auth/register",
            json={
                "email": "reporter@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        token = reg_response.json()["access_token"]
        
        # Submit report
        response = client.post(
            "/reports/",
            json={
                "text": "Heavy waterlogging near MG Road, Jabalpur",
                "city": "Jabalpur",
                "state": "Madhya Pradesh",
                "latitude": 23.1815,
                "longitude": 79.9864,
                "event_type": "FLOODING",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "report_id" in data
        assert "event_id" in data
        assert data["verification_status"] == "UNVERIFIED"
        # Evidence status should be set
        assert data["evidence_status"] in {
            "SUPPORTED",
            "CONFLICTING",
            "UNVERIFIED",
            "INSUFFICIENT_EVIDENCE",
        }
    
    def test_submit_report_missing_required_field(self, client):
        """Test validation of required fields."""
        # Register and login
        reg_response = client.post(
            "/auth/register",
            json={
                "email": "reporter2@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        token = reg_response.json()["access_token"]
        
        # Submit report without text (required)
        response = client.post(
            "/reports/",
            json={
                "city": "Jabalpur",
                "state": "Madhya Pradesh",
                "latitude": 23.1815,
                "longitude": 79.9864,
                "event_type": "FLOODING",
                # Missing: text
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_submit_report_invalid_coordinates(self, client):
        """Test validation of coordinates."""
        # Register and login
        reg_response = client.post(
            "/auth/register",
            json={
                "email": "reporter3@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        token = reg_response.json()["access_token"]
        
        # Submit report with invalid latitude
        response = client.post(
            "/reports/",
            json={
                "text": "Test report",
                "city": "Jabalpur",
                "latitude": 999.0,  # Invalid
                "longitude": 79.9864,
                "event_type": "FLOODING",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 422  # Validation error


class TestReportStatus:
    """Test GET /reports/{id}/status endpoint."""
    
    def test_get_report_status(self, client):
        """Test retrieving report status."""
        # Register and login
        reg_response = client.post(
            "/auth/register",
            json={
                "email": "statuschecker@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        token = reg_response.json()["access_token"]
        
        # Submit report
        submit_response = client.post(
            "/reports/",
            json={
                "text": "Test weather report",
                "city": "Jabalpur",
                "state": "Madhya Pradesh",
                "latitude": 23.1815,
                "longitude": 79.9864,
                "event_type": "RAINFALL",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        report_id = submit_response.json()["report_id"]
        
        # Query status
        response = client.get(
            f"/reports/{report_id}/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert str(data["report_id"]) == report_id
        assert data["text"] == "Test weather report"
        assert data["city"] == "Jabalpur"
    
    def test_citizen_cannot_access_other_citizens_report(self, client):
        """Test that Citizen A cannot access Citizen B's report (ownership enforcement).

        This exercises phase5/api/routes/reports.py's explicit CITIZEN
        ownership check (403 when author_id_or_hash does not match the
        requesting user), which previously had no automated test coverage.
        """
        # Citizen A registers and submits a report
        citizen_a = client.post(
            "/auth/register",
            json={
                "email": "citizen_a_owner@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        token_a = citizen_a.json()["access_token"]

        submit_response = client.post(
            "/reports/",
            json={
                "text": "Citizen A's private report",
                "city": "Jabalpur",
                "state": "Madhya Pradesh",
                "latitude": 23.1815,
                "longitude": 79.9864,
                "event_type": "RAINFALL",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        report_id = submit_response.json()["report_id"]

        # Citizen B registers and tries to read Citizen A's report
        citizen_b = client.post(
            "/auth/register",
            json={
                "email": "citizen_b_intruder@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        token_b = citizen_b.json()["access_token"]

        response = client.get(
            f"/reports/{report_id}/status",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        assert response.status_code == 403

        # Sanity check: Citizen A can still access their own report
        own_response = client.get(
            f"/reports/{report_id}/status",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert own_response.status_code == 200

    def test_get_nonexistent_report(self, client):
        """Test querying nonexistent report."""
        # Register and login
        reg_response = client.post(
            "/auth/register",
            json={
                "email": "notfound@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        token = reg_response.json()["access_token"]
        
        # Try to get nonexistent report
        response = client.get(
            "/reports/00000000-0000-0000-0000-000000000000/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 404


class TestEventQuerying:
    """Test event listing and detail endpoints."""
    
    def test_list_events_citizen_only_sees_verified(self, client):
        """Test that citizens only see verified events."""
        # Register and login as citizen
        citizen_response = client.post(
            "/auth/register",
            json={
                "email": "eventcitizen@test.com",
                "password": "TestPassword123!",
                "role": "CITIZEN",
            },
        )
        citizen_token = citizen_response.json()["access_token"]
        
        # List events
        response = client.get(
            "/events",
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "total" in data
        # For now, no verified events should exist yet
        assert data["total"] >= 0
    
    def test_list_events_with_filters(self, client, db_session):
        """Test event listing with various filters."""
        # Provision an analyst directly for this RBAC test. Public registration
        # intentionally creates CITIZEN accounts only.
        # NOTE: db_session must be requested as an explicit fixture argument
        # here (not just relied on indirectly via `client`), otherwise the
        # bare name `db_session` inside this function resolves to the
        # module-level fixture *function* object, not a session instance,
        # and `db_session.add(...)` fails with AttributeError.
        from phase5.api.auth.jwt_handler import create_tokens_for_user, JWTHandler
        analyst = User(
            email="eventanalyst@test.com",
            password_hash=JWTHandler.hash_password("TestPassword123!"),
            role="ANALYST",
        )
        db_session.add(analyst)
        db_session.commit()
        db_session.refresh(analyst)
        analyst_token = create_tokens_for_user(
            user_id=str(analyst.user_id),
            email=analyst.email,
            role=analyst.role,
        )["access_token"]
        
        # List events with severity filter
        response = client.get(
            "/events?severity=HIGH&limit=10",
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["events"], list)


class TestHealthAndMetadata:
    """Test health and metadata endpoints."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_root_endpoint(self, client):
        """Test root endpoint metadata."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["processing_model"] == "Synchronous (no async queue)"


if __name__ == "__main__":
    # Run with: pytest phase5/tests/test_phase5_integration.py -v
    pytest.main([__file__, "-v"])
