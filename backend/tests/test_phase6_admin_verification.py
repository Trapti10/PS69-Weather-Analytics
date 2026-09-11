"""
Phase 6 Integration Tests: Admin Verification Workflow

Covers the 21 scenarios from the Phase 6 brief:
- Authentication/Authorization (1-8)
- Verification behavior (9-17)
- Persistence (18-20)
- Regression (21) is verified separately by running the whole backend/tests/
  suite together (see PS69_HANDOFF_DOCUMENT.md) - existing Phase 5 tests are
  not touched or duplicated here.

Fixtures intentionally mirror test_phase5_integration.py's test_db/db_session/
client pattern exactly (same DB name, same failure-is-fatal philosophy) but are
defined locally in this file rather than factored into a shared conftest.py,
so this new test file has zero coupling to - and makes zero changes to -
the existing Phase 5 test file.

Tests assume PostgreSQL + PostGIS is running on localhost:5432 (same
ps69_weather_test database Phase 5 already uses).
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker

from backend.api.main import app
from backend.api.db import Base, get_db
from backend.api.models import User, WeatherEvent, WeatherReport, AdminReviewAction, AuditLog
from backend.api.auth.jwt_handler import JWTHandler, create_tokens_for_user

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://ps69_admin:ps69_password_dev@localhost:5432/ps69_weather_test",
)


@pytest.fixture(scope="session")
def test_db():
    """Create the dedicated PostgreSQL test database and its tables.

    Same philosophy as Phase 5: database unavailability is a hard failure,
    not a skip, because Phase 6 acceptance requires real PostgreSQL/PostGIS
    integration tests to execute.
    """
    engine = None
    admin_engine = None
    try:
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

        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.commit()

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
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# HELPERS
# ============================================================================

def _make_user(db_session, email: str, role: str) -> tuple[User, str]:
    """Provision a user directly in the DB (bypassing public registration,
    which is intentionally CITIZEN-only) and return (user, access_token)."""
    user = User(
        email=email,
        password_hash=JWTHandler.hash_password("TestPassword123!"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_tokens_for_user(
        user_id=str(user.user_id), email=user.email, role=user.role
    )["access_token"]
    return user, token


def _make_event(db_session, **overrides) -> WeatherEvent:
    """Create a WeatherEvent directly in the DB with sensible defaults."""
    defaults = dict(
        event_type="RAINFALL",
        location_name="Jabalpur, Madhya Pradesh",
        severity="HIGH",
        start_time=datetime.now(timezone.utc) - timedelta(hours=1),
        evidence_status="CONFLICTING",
        evidence_support_score=0.42,
        evidence_detail={
            "verification_reasons": ["ERA5 supports, IMD conflicts"],
            "source_evidence": {"ERA5": "SUPPORTING", "IMD": "CONFLICTING"},
        },
        final_verification_status="NEEDS_REVIEW",
        member_report_ids=[],
        report_count=2,
        unique_sources=2,
    )
    defaults.update(overrides)
    event = WeatherEvent(**defaults)
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


def _make_report(db_session, event: WeatherEvent, **overrides) -> WeatherReport:
    defaults = dict(
        source_type="CITIZEN_REPORT",
        source_name="test_fixture",
        author_id_or_hash="user:fixture",
        report_timestamp=datetime.now(timezone.utc),
        city="Jabalpur",
        state="Madhya Pradesh",
        text="Heavy rainfall reported near MG Road",
        event_type="RAINFALL",
        verification_status="UNVERIFIED",
        source_reliability=0.7,
        event_id=event.event_id,
    )
    defaults.update(overrides)
    report = WeatherReport(**defaults)
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


# ============================================================================
# 1-8: AUTHENTICATION / AUTHORIZATION
# ============================================================================

class TestAdminAuthorization:

    def test_01_unauthenticated_cannot_access_queue(self, client):
        response = client.get("/admin/verification-queue")
        assert response.status_code == 401

    def test_02_citizen_cannot_access_queue(self, client):
        reg = client.post(
            "/auth/register",
            json={"email": "queue_citizen@test.com", "password": "TestPassword123!", "role": "CITIZEN"},
        )
        token = reg.json()["access_token"]
        response = client.get(
            "/admin/verification-queue", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    def test_03_analyst_cannot_access_queue(self, client, db_session):
        _, token = _make_user(db_session, "queue_analyst@test.com", "ANALYST")
        response = client.get(
            "/admin/verification-queue", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    def test_04_citizen_cannot_verify(self, client, db_session):
        event = _make_event(db_session)
        reg = client.post(
            "/auth/register",
            json={"email": "verify_citizen@test.com", "password": "TestPassword123!", "role": "CITIZEN"},
        )
        token = reg.json()["access_token"]
        response = client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "VERIFIED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_05_analyst_cannot_verify(self, client, db_session):
        event = _make_event(db_session)
        _, token = _make_user(db_session, "verify_analyst@test.com", "ANALYST")
        response = client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "VERIFIED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_06_admin_can_access_queue(self, client, db_session):
        _make_event(db_session)
        _, token = _make_user(db_session, "queue_admin@test.com", "ADMIN")
        response = client.get(
            "/admin/verification-queue", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data and "total" in data

    def test_07_admin_can_inspect_evidence(self, client, db_session):
        event = _make_event(db_session)
        _make_report(db_session, event)
        _, token = _make_user(db_session, "evidence_admin@test.com", "ADMIN")
        response = client.get(
            f"/admin/events/{event.event_id}/evidence",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event"]["event_id"] == str(event.event_id)
        assert len(data["reports"]) == 1
        assert data["external_evidence"] is not None

    def test_08_admin_can_verify(self, client, db_session):
        event = _make_event(db_session)
        _, token = _make_user(db_session, "verify_admin@test.com", "ADMIN")
        response = client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "VERIFIED", "notes": "Corroborated by ERA5 and multiple citizen reports."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200


# ============================================================================
# 9-17: VERIFICATION BEHAVIOR
# ============================================================================

class TestVerificationDecisions:

    def test_09_verified_works(self, client, db_session):
        event = _make_event(db_session)
        _, token = _make_user(db_session, "dec_verified@test.com", "ADMIN")
        response = client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "VERIFIED", "notes": "Confirmed by IMD."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["final_verification_status"] == "VERIFIED"

    def test_10_needs_review_works(self, client, db_session):
        event = _make_event(db_session, final_verification_status="VERIFIED")
        _, token = _make_user(db_session, "dec_needsreview@test.com", "ADMIN")
        response = client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "NEEDS_REVIEW", "notes": "New conflicting report came in, reopening."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["final_verification_status"] == "NEEDS_REVIEW"

    def test_11_rejected_works(self, client, db_session):
        event = _make_event(db_session)
        _, token = _make_user(db_session, "dec_rejected@test.com", "ADMIN")
        response = client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "REJECTED", "notes": "No corroborating evidence from any source."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["final_verification_status"] == "REJECTED"

    def test_12_invalid_status_rejected(self, client, db_session):
        event = _make_event(db_session)
        _, token = _make_user(db_session, "dec_invalid@test.com", "ADMIN")
        response = client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "FAKE", "notes": "n/a"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_13_nonexistent_event_rejected(self, client, db_session):
        _, token = _make_user(db_session, "dec_noevent@test.com", "ADMIN")
        response = client.post(
            f"/admin/events/{uuid4()}/verify",
            json={"action": "VERIFIED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_14_reason_validation(self, client, db_session):
        event_a = _make_event(db_session)
        event_b = _make_event(db_session)
        event_c = _make_event(db_session)
        _, token = _make_user(db_session, "dec_reason@test.com", "ADMIN")

        # REJECTED without notes -> 422
        r1 = client.post(
            f"/admin/events/{event_a.event_id}/verify",
            json={"action": "REJECTED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 422

        # NEEDS_REVIEW without notes -> 422
        r2 = client.post(
            f"/admin/events/{event_b.event_id}/verify",
            json={"action": "NEEDS_REVIEW"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 422

        # VERIFIED without notes -> allowed (notes optional for VERIFIED)
        r3 = client.post(
            f"/admin/events/{event_c.event_id}/verify",
            json={"action": "VERIFIED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r3.status_code == 200

    def test_15_previous_status_captured(self, client, db_session):
        event = _make_event(db_session, final_verification_status="NEEDS_REVIEW")
        _, token = _make_user(db_session, "dec_prevstatus@test.com", "ADMIN")
        response = client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "VERIFIED", "notes": "Confirmed."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["previous_status"] == "NEEDS_REVIEW"
        assert data["final_verification_status"] == "VERIFIED"

    def test_16_admin_review_action_created(self, client, db_session):
        event = _make_event(db_session)
        admin_user, token = _make_user(db_session, "dec_reviewaction@test.com", "ADMIN")
        client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "REJECTED", "notes": "Insufficient corroboration."},
            headers={"Authorization": f"Bearer {token}"},
        )
        actions = db_session.execute(
            select(AdminReviewAction).where(AdminReviewAction.event_id == event.event_id)
        ).scalars().all()
        assert len(actions) == 1
        assert actions[0].admin_id == admin_user.user_id
        assert actions[0].action == "REJECTED"
        assert actions[0].notes == "Insufficient corroboration."

    def test_17_audit_log_created(self, client, db_session):
        event = _make_event(db_session)
        admin_user, token = _make_user(db_session, "dec_auditlog@test.com", "ADMIN")
        client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "VERIFIED", "notes": "Confirmed by multiple sources."},
            headers={"Authorization": f"Bearer {token}"},
        )
        logs = db_session.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "WEATHER_EVENT",
                AuditLog.entity_id == event.event_id,
            )
        ).scalars().all()
        assert len(logs) == 1
        assert logs[0].actor_id == admin_user.user_id
        assert logs[0].action == "VERIFIED"


# ============================================================================
# 18-20: PERSISTENCE
# ============================================================================

class TestPersistence:

    def test_18_decision_survives_reload(self, client, db_session, test_db):
        event = _make_event(db_session)
        _, token = _make_user(db_session, "persist_reload@test.com", "ADMIN")
        client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "VERIFIED", "notes": "Confirmed."},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Open a brand new session/connection against the same database to
        # rule out any in-memory session caching masking a persistence bug.
        FreshSession = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
        fresh = FreshSession()
        try:
            reloaded = fresh.execute(
                select(WeatherEvent).where(WeatherEvent.event_id == event.event_id)
            ).scalars().first()
            assert reloaded is not None
            assert reloaded.final_verification_status == "VERIFIED"
            assert reloaded.review_notes == "Confirmed."
            assert reloaded.reviewed_by is not None
            assert reloaded.reviewed_at is not None
        finally:
            fresh.close()

    def test_19_audit_data_matches_verification_action(self, client, db_session):
        event = _make_event(db_session, final_verification_status="NEEDS_REVIEW")
        admin_user, token = _make_user(db_session, "persist_auditmatch@test.com", "ADMIN")
        response = client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "REJECTED", "notes": "Evidence does not support this report."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        log = db_session.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "WEATHER_EVENT",
                AuditLog.entity_id == event.event_id,
            )
        ).scalars().first()
        assert log.changes["previous_status"] == "NEEDS_REVIEW"
        assert log.changes["new_status"] == "REJECTED"
        assert log.changes["notes"] == "Evidence does not support this report."

        review_action = db_session.execute(
            select(AdminReviewAction).where(AdminReviewAction.event_id == event.event_id)
        ).scalars().first()
        assert review_action.action == "REJECTED"
        assert review_action.notes == "Evidence does not support this report."
        assert review_action.evidence_summary["evidence_status"] == event.evidence_status

    def test_20_no_partial_writes_on_validation_failure(self, client, db_session):
        """
        Transaction-safety, tested at the boundary that's actually reachable
        from a test: a request that fails validation (missing required reason)
        must not create an AdminReviewAction, an AuditLog row, or touch the
        event's final_verification_status at all.

        Simulating a genuine mid-transaction database failure (e.g. the
        connection dropping between the AdminReviewAction insert and the
        AuditLog insert) isn't practical to trigger deterministically in this
        test environment, so this is documented here as the tested boundary
        rather than claimed as full fault-injection coverage.
        """
        event = _make_event(db_session, final_verification_status="NEEDS_REVIEW")
        _, token = _make_user(db_session, "persist_rollback@test.com", "ADMIN")

        response = client.post(
            f"/admin/events/{event.event_id}/verify",
            json={"action": "REJECTED"},  # missing required notes -> 422
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

        db_session.refresh(event)
        assert event.final_verification_status == "NEEDS_REVIEW"  # unchanged

        actions = db_session.execute(
            select(AdminReviewAction).where(AdminReviewAction.event_id == event.event_id)
        ).scalars().all()
        assert len(actions) == 0

        logs = db_session.execute(
            select(AuditLog).where(AuditLog.entity_id == event.event_id)
        ).scalars().all()
        assert len(logs) == 0


# ============================================================================
# BONUS: QUEUE FILTERING (not in the numbered list, but directly required by
# section 5 of the brief - included for real coverage of the filter behavior)
# ============================================================================

class TestQueueFiltering:

    def test_queue_default_shows_only_needs_review(self, client, db_session):
        needs_review_event = _make_event(db_session, final_verification_status="NEEDS_REVIEW")
        verified_event = _make_event(db_session, final_verification_status="VERIFIED")
        _, token = _make_user(db_session, "queuefilter_default@test.com", "ADMIN")

        response = client.get(
            "/admin/verification-queue", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        ids = {item["event_id"] for item in response.json()["items"]}
        assert str(needs_review_event.event_id) in ids
        assert str(verified_event.event_id) not in ids

    def test_queue_status_all_shows_everything(self, client, db_session):
        e1 = _make_event(db_session, final_verification_status="NEEDS_REVIEW")
        e2 = _make_event(db_session, final_verification_status="VERIFIED")
        _, token = _make_user(db_session, "queuefilter_all@test.com", "ADMIN")

        response = client.get(
            "/admin/verification-queue?status=ALL",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        ids = {item["event_id"] for item in response.json()["items"]}
        assert str(e1.event_id) in ids
        assert str(e2.event_id) in ids

    def test_queue_evidence_status_filter(self, client, db_session):
        conflicting = _make_event(db_session, evidence_status="CONFLICTING")
        supported = _make_event(db_session, evidence_status="SUPPORTED")
        _, token = _make_user(db_session, "queuefilter_evidence@test.com", "ADMIN")

        response = client.get(
            "/admin/verification-queue?status=ALL&evidence_status=CONFLICTING",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        ids = {item["event_id"] for item in response.json()["items"]}
        assert str(conflicting.event_id) in ids
        assert str(supported.event_id) not in ids

    def test_queue_invalid_status_filter_rejected(self, client, db_session):
        _, token = _make_user(db_session, "queuefilter_invalid@test.com", "ADMIN")
        response = client.get(
            "/admin/verification-queue?status=FAKE",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
