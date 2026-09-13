"""
Analytics module tests: database-backed weather intelligence endpoints
(backend/api/routes/analytics.py) and ingestion (backend/db/ingest_analytics_data.py).

Fixtures mirror test_phase6_admin_verification.py's test_db/db_session/client
pattern exactly (same DB, same fail-hard-if-no-postgres philosophy), defined
locally so this file has zero coupling to other test files.
"""

import csv
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.api.main import app
from backend.api.db import Base, get_db
from backend.api.models import (
    User,
    WeatherEvent,
    WeatherObservation,
    WeatherAnomaly,
    WeatherReport,
    AdminReviewAction,
    Alert,
    AuditLog,
)
from backend.api.auth.jwt_handler import JWTHandler, create_tokens_for_user
from backend.db.ingest_analytics_data import ingest_observations, ingest_anomalies

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://ps69_admin:ps69_password_dev@localhost:5432/ps69_weather_test",
)


@pytest.fixture(scope="session")
def test_db():
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
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
    session = TestingSessionLocal()
    yield session
    # Analytics tables aren't touched by other test files, but tests within
    # this file share the session-scoped database - clean up after every
    # test so aggregation assertions never see another test's rows.
    session.rollback()
    # Delete in FK-safe order. schema.sql declares ON DELETE CASCADE for
    # admin_review_actions/alerts -> weather_events, but the test database is
    # actually built from the SQLAlchemy ORM metadata (Base.metadata.create_all
    # in the test_db fixture above), and those ORM Column(..., ForeignKey(...))
    # definitions in models.py don't carry ondelete="CASCADE" - so in this
    # test database plain FK-restrict behavior applies and children must be
    # deleted explicitly before their parent. This also mops up any leftover
    # rows from other test files that share this session-scoped database
    # within one pytest run.
    session.query(AdminReviewAction).delete()
    session.query(Alert).delete()
    session.query(WeatherReport).delete()
    session.query(WeatherEvent).delete()
    session.query(WeatherObservation).delete()
    session.query(WeatherAnomaly).delete()
    session.query(AuditLog).delete()
    session.query(User).delete()
    session.commit()
    session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# HELPERS
# ============================================================================

def _make_user(db_session, email: str, role: str):
    user = User(email=email, password_hash=JWTHandler.hash_password("TestPassword123!"), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_tokens_for_user(user_id=str(user.user_id), email=user.email, role=user.role)["access_token"]
    return user, token


def _make_observation(db_session, **overrides) -> WeatherObservation:
    defaults = dict(
        id=str(uuid4()),
        source="ERA5",
        observed_at=datetime(2024, 6, 1, 12, tzinfo=timezone.utc),
        latitude=23.25,
        longitude=80.0,
        location_name="Jabalpur, Madhya Pradesh",
        temperature=30.0,
        humidity=None,
        rainfall=0.0,
        wind_speed=2.0,
        wind_direction=180.0,
        pressure=1000.0,
        verification_status="validated",
        confidence_score=0.85,
    )
    defaults.update(overrides)
    obs = WeatherObservation(**defaults)
    db_session.add(obs)
    db_session.commit()
    return obs


def _make_anomaly(db_session, **overrides) -> WeatherAnomaly:
    defaults = dict(
        id=str(uuid4()),
        source="ERA5",
        observed_at=datetime(2024, 7, 8, 8, tzinfo=timezone.utc),
        detected_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        variable="temperature",
        observed_value=32.1,
        baseline_value=27.3,
        deviation=4.8,
        method="rolling_zscore",
        threshold=3.0,
        anomaly_score=3.1,
        severity="LOW",
        classification="STATISTICAL_ANOMALY",
        status="EVALUATED",
        explanation="test anomaly",
        latitude=23.25,
        longitude=80.0,
        location_name="Jabalpur, Madhya Pradesh",
    )
    defaults.update(overrides)
    anomaly = WeatherAnomaly(**defaults)
    db_session.add(anomaly)
    db_session.commit()
    return anomaly


def _make_event(db_session, **overrides) -> WeatherEvent:
    defaults = dict(
        event_type="RAINFALL",
        location_name="Jabalpur, Madhya Pradesh",
        severity="HIGH",
        start_time=datetime.now(timezone.utc) - timedelta(hours=1),
        evidence_status="SUPPORTED",
        evidence_support_score=0.9,
        final_verification_status="VERIFIED",
        member_report_ids=[],
        report_count=1,
        unique_sources=1,
    )
    defaults.update(overrides)
    event = WeatherEvent(**defaults)
    db_session.add(event)
    db_session.commit()
    return event


# ============================================================================
# AUTHORIZATION
# ============================================================================

class TestAnalyticsAuthorization:

    def test_unauthenticated_cannot_access_overview(self, client):
        response = client.get("/analytics/overview")
        assert response.status_code == 401

    def test_citizen_cannot_access_overview(self, client):
        reg = client.post(
            "/auth/register",
            json={"email": "analytics_citizen@test.com", "password": "TestPassword123!"},
        )
        token = reg.json()["access_token"]
        response = client.get("/analytics/overview", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    def test_analyst_can_access_overview(self, client, db_session):
        _, token = _make_user(db_session, "analytics_analyst@test.com", "ANALYST")
        response = client.get("/analytics/overview", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    def test_admin_can_access_overview(self, client, db_session):
        _, token = _make_user(db_session, "analytics_admin@test.com", "ADMIN")
        response = client.get("/analytics/overview", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/analytics/overview",
            "/analytics/weather-trends",
            "/analytics/rainfall",
            "/analytics/temperature",
            "/analytics/source-comparison",
            "/analytics/anomalies",
            "/analytics/event-distribution",
            "/analytics/verification",
        ],
    )
    def test_citizen_forbidden_from_every_analytics_endpoint(self, client, endpoint):
        reg = client.post(
            "/auth/register",
            json={"email": f"citizen_{endpoint.replace('/', '_')}@test.com", "password": "TestPassword123!"},
        )
        token = reg.json()["access_token"]
        response = client.get(endpoint, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


# ============================================================================
# EMPTY STATE
# ============================================================================

class TestAnalyticsEmptyState:
    """No fabricated numbers: an empty database must return real zeros/empty
    lists, never an error and never made-up figures."""

    def test_overview_empty_state(self, client, db_session):
        _, token = _make_user(db_session, "empty_overview@test.com", "ANALYST")
        response = client.get("/analytics/overview", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        body = response.json()
        assert body["total_weather_observations"] == 0
        assert body["total_anomalies"] == 0
        assert body["total_weather_events"] == 0
        assert body["average_temperature"] is None

    def test_event_distribution_empty_state(self, client, db_session):
        _, token = _make_user(db_session, "empty_dist@test.com", "ANALYST")
        response = client.get("/analytics/event-distribution", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        body = response.json()
        assert body["total_events"] == 0
        assert body["by_event_type"] == []


# ============================================================================
# AGGREGATION CORRECTNESS
# ============================================================================

class TestAnalyticsAggregation:

    def test_overview_totals_and_averages(self, client, db_session):
        _make_observation(db_session, source="ERA5", temperature=20.0, rainfall=5.0)
        _make_observation(db_session, source="Open-Meteo", temperature=30.0, rainfall=15.0)
        _make_anomaly(db_session)
        _make_event(db_session, final_verification_status="VERIFIED")
        _make_event(db_session, final_verification_status="NEEDS_REVIEW")

        _, token = _make_user(db_session, "agg_overview@test.com", "ANALYST")
        response = client.get("/analytics/overview", headers={"Authorization": f"Bearer {token}"})
        body = response.json()

        assert body["total_weather_observations"] == 2
        assert body["total_sources"] == 2
        assert body["total_anomalies"] == 1
        assert body["total_weather_events"] == 2
        assert body["verified_events"] == 1
        assert body["needs_review"] == 1
        assert body["average_temperature"] == 25.0  # (20+30)/2, computed by SQL AVG not Python
        assert body["max_temperature"] == 30.0
        assert body["total_rainfall"] == 20.0

    def test_source_comparison_groups_by_source(self, client, db_session):
        _make_observation(db_session, source="ERA5", temperature=20.0, rainfall=1.0)
        _make_observation(db_session, source="ERA5", temperature=22.0, rainfall=1.0)
        _make_observation(db_session, source="Open-Meteo", temperature=30.0, rainfall=2.0, humidity=50.0)

        _, token = _make_user(db_session, "agg_source@test.com", "ANALYST")
        response = client.get("/analytics/source-comparison", headers={"Authorization": f"Bearer {token}"})
        sources = {s["source"]: s for s in response.json()["sources"]}

        assert sources["ERA5"]["observation_count"] == 2
        assert sources["ERA5"]["average_temperature"] == 21.0
        assert sources["Open-Meteo"]["observation_count"] == 1
        assert sources["Open-Meteo"]["average_humidity"] == 50.0

    def test_weather_trends_buckets_by_day(self, client, db_session):
        _make_observation(db_session, observed_at=datetime(2024, 6, 1, 3, tzinfo=timezone.utc), temperature=10.0)
        _make_observation(db_session, observed_at=datetime(2024, 6, 1, 15, tzinfo=timezone.utc), temperature=20.0)
        _make_observation(db_session, observed_at=datetime(2024, 6, 2, 3, tzinfo=timezone.utc), temperature=40.0)

        _, token = _make_user(db_session, "agg_trends@test.com", "ANALYST")
        response = client.get("/analytics/weather-trends", headers={"Authorization": f"Bearer {token}"})
        trends = {t["date"]: t for t in response.json()["trends"]}

        assert trends["2024-06-01"]["observation_count"] == 2
        assert trends["2024-06-01"]["average_temperature"] == 15.0
        assert trends["2024-06-02"]["observation_count"] == 1
        assert trends["2024-06-02"]["average_temperature"] == 40.0

    def test_rainfall_totals_and_max_day(self, client, db_session):
        _make_observation(db_session, observed_at=datetime(2024, 6, 1, 3, tzinfo=timezone.utc), rainfall=5.0)
        _make_observation(db_session, observed_at=datetime(2024, 6, 2, 3, tzinfo=timezone.utc), rainfall=25.0)

        _, token = _make_user(db_session, "agg_rain@test.com", "ANALYST")
        response = client.get("/analytics/rainfall", headers={"Authorization": f"Bearer {token}"})
        body = response.json()

        assert body["total_rainfall"] == 30.0
        assert body["max_daily_rainfall"] == 25.0

    def test_temperature_min_max(self, client, db_session):
        _make_observation(db_session, temperature=5.0)
        _make_observation(db_session, temperature=45.0)

        _, token = _make_user(db_session, "agg_temp@test.com", "ANALYST")
        response = client.get("/analytics/temperature", headers={"Authorization": f"Bearer {token}"})
        body = response.json()

        assert body["min_temperature"] == 5.0
        assert body["max_temperature"] == 45.0

    def test_anomalies_grouped_by_variable_and_severity(self, client, db_session):
        _make_anomaly(db_session, variable="temperature", severity="LOW")
        _make_anomaly(db_session, variable="temperature", severity="LOW")
        _make_anomaly(db_session, variable="rainfall", severity="CRITICAL")

        _, token = _make_user(db_session, "agg_anom@test.com", "ANALYST")
        response = client.get("/analytics/anomalies", headers={"Authorization": f"Bearer {token}"})
        body = response.json()

        assert body["total_anomalies"] == 3
        groups = {(g["variable"], g["severity"]): g["count"] for g in body["by_variable_severity"]}
        assert groups[("temperature", "LOW")] == 2
        assert groups[("rainfall", "CRITICAL")] == 1
        assert len(body["latest"]) == 3

    def test_anomalies_filter_by_severity(self, client, db_session):
        _make_anomaly(db_session, severity="LOW")
        _make_anomaly(db_session, severity="CRITICAL")

        _, token = _make_user(db_session, "agg_anom_filter@test.com", "ANALYST")
        response = client.get(
            "/analytics/anomalies", params={"severity": "CRITICAL"}, headers={"Authorization": f"Bearer {token}"}
        )
        body = response.json()
        assert body["total_anomalies"] == 1
        assert body["by_severity"] == [{"severity": "CRITICAL", "count": 1}]

    def test_event_distribution_groups_by_type_and_severity(self, client, db_session):
        _make_event(db_session, event_type="RAINFALL", severity="HIGH")
        _make_event(db_session, event_type="RAINFALL", severity="HIGH")
        _make_event(db_session, event_type="HEATWAVE", severity="EXTREME")

        _, token = _make_user(db_session, "agg_dist@test.com", "ANALYST")
        response = client.get("/analytics/event-distribution", headers={"Authorization": f"Bearer {token}"})
        body = response.json()

        by_type = {t["event_type"]: t["count"] for t in body["by_event_type"]}
        assert by_type["RAINFALL"] == 2
        assert by_type["HEATWAVE"] == 1

    def test_verification_counts(self, client, db_session):
        _make_event(db_session, final_verification_status="VERIFIED")
        _make_event(db_session, final_verification_status="VERIFIED")
        _make_event(db_session, final_verification_status="NEEDS_REVIEW")
        _make_event(db_session, final_verification_status="REJECTED")

        _, token = _make_user(db_session, "agg_verify@test.com", "ANALYST")
        response = client.get("/analytics/verification", headers={"Authorization": f"Bearer {token}"})
        body = response.json()

        assert body["total_events"] == 4
        assert body["verified"] == 2
        assert body["needs_review"] == 1
        assert body["rejected"] == 1


# ============================================================================
# DATE / SOURCE FILTERING
# ============================================================================

class TestAnalyticsFiltering:

    def test_weather_trends_source_filter(self, client, db_session):
        _make_observation(db_session, source="ERA5", temperature=10.0)
        _make_observation(db_session, source="Open-Meteo", temperature=99.0)

        _, token = _make_user(db_session, "filter_source@test.com", "ANALYST")
        response = client.get(
            "/analytics/weather-trends", params={"source": "ERA5"}, headers={"Authorization": f"Bearer {token}"}
        )
        trends = response.json()["trends"]
        assert len(trends) == 1
        assert trends[0]["average_temperature"] == 10.0

    def test_weather_trends_date_range_filter(self, client, db_session):
        _make_observation(db_session, observed_at=datetime(2024, 1, 1, tzinfo=timezone.utc), temperature=1.0)
        _make_observation(db_session, observed_at=datetime(2024, 6, 1, tzinfo=timezone.utc), temperature=2.0)
        _make_observation(db_session, observed_at=datetime(2024, 12, 1, tzinfo=timezone.utc), temperature=3.0)

        _, token = _make_user(db_session, "filter_date@test.com", "ANALYST")
        response = client.get(
            "/analytics/weather-trends",
            params={"start_date": "2024-05-01T00:00:00Z", "end_date": "2024-07-01T00:00:00Z"},
            headers={"Authorization": f"Bearer {token}"},
        )
        trends = response.json()["trends"]
        assert len(trends) == 1
        assert trends[0]["date"] == "2024-06-01"

    def test_event_distribution_date_range_filter(self, client, db_session):
        _make_event(db_session, event_type="OLD", start_time=datetime(2020, 1, 1, tzinfo=timezone.utc))
        _make_event(db_session, event_type="NEW", start_time=datetime.now(timezone.utc))

        _, token = _make_user(db_session, "filter_event_date@test.com", "ANALYST")
        response = client.get(
            "/analytics/event-distribution",
            params={"start_date": "2024-01-01T00:00:00Z"},
            headers={"Authorization": f"Bearer {token}"},
        )
        body = response.json()
        by_type = {t["event_type"] for t in body["by_event_type"]}
        assert "NEW" in by_type
        assert "OLD" not in by_type


# ============================================================================
# INGESTION: idempotency, validation, malformed-row handling
# ============================================================================

class TestIngestion:

    def _write_csv(self, tmp_path, rows, fieldnames):
        path = tmp_path / "obs.csv"
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return path

    def test_observation_ingestion_is_idempotent(self, test_db, db_session, tmp_path):
        fieldnames = [
            "id", "source", "timestamp", "latitude", "longitude", "temperature",
            "pressure", "rainfall", "wind_speed", "wind_direction",
            "verification_status", "confidence_score", "quality_flags",
        ]
        row = {
            "id": str(uuid4()), "source": "ERA5", "timestamp": "2024-01-01T00:00:00Z",
            "latitude": "23.25", "longitude": "80.0", "temperature": "20.0",
            "pressure": "1000", "rainfall": "0.0", "wind_speed": "1.0",
            "wind_direction": "180", "verification_status": "validated",
            "confidence_score": "0.9", "quality_flags": "",
        }
        path = self._write_csv(tmp_path, [row], fieldnames)

        stats1 = ingest_observations(path, TEST_DATABASE_URL)
        assert stats1 == {"read": 1, "inserted": 1, "skipped_existing": 0, "failed": 0, "errors": []}

        stats2 = ingest_observations(path, TEST_DATABASE_URL)
        assert stats2["inserted"] == 0
        assert stats2["skipped_existing"] == 1

        count = db_session.query(WeatherObservation).filter(WeatherObservation.id == row["id"]).count()
        assert count == 1

    def test_observation_ingestion_skips_malformed_rows_without_failing_the_batch(self, tmp_path):
        fieldnames = [
            "id", "source", "timestamp", "latitude", "longitude", "temperature",
            "pressure", "rainfall", "wind_speed", "wind_direction",
            "verification_status", "confidence_score", "quality_flags",
        ]
        good_row = {
            "id": str(uuid4()), "source": "ERA5", "timestamp": "2024-01-01T00:00:00Z",
            "latitude": "23.25", "longitude": "80.0", "temperature": "20.0",
            "pressure": "1000", "rainfall": "0.0", "wind_speed": "1.0",
            "wind_direction": "180", "verification_status": "validated",
            "confidence_score": "0.9", "quality_flags": "",
        }
        bad_row = dict(good_row, id=str(uuid4()), timestamp="not-a-timestamp")
        no_id_row = dict(good_row, id="")
        path = self._write_csv(tmp_path, [good_row, bad_row, no_id_row], fieldnames)

        stats = ingest_observations(path, TEST_DATABASE_URL)
        assert stats["read"] == 3
        assert stats["inserted"] == 1
        assert stats["failed"] == 2

    def test_ingestion_rejects_file_missing_required_columns(self, tmp_path):
        path = tmp_path / "bad.csv"
        with open(path, "w", newline="") as f:
            f.write("foo,bar\n1,2\n")

        stats = ingest_observations(path, TEST_DATABASE_URL)
        assert stats["failed"] >= 1

    def test_anomaly_ingestion_is_idempotent_and_validates_severity(self, test_db, db_session, tmp_path):
        fieldnames = [
            "id", "generated_at", "timestamp", "latitude", "longitude", "location",
            "source", "variable", "observed_value", "baseline_value", "deviation",
            "method", "threshold", "anomaly_score", "severity", "classification",
            "status", "explanation",
        ]
        good_row = {
            "id": str(uuid4()), "generated_at": "2026-09-01T00:00:00Z", "timestamp": "2024-07-08T08:00:00Z",
            "latitude": "23.25", "longitude": "80.0", "location": "India", "source": "ERA5",
            "variable": "temperature", "observed_value": "32.1", "baseline_value": "27.3",
            "deviation": "4.8", "method": "rolling_zscore", "threshold": "3.0",
            "anomaly_score": "3.1", "severity": "LOW", "classification": "STATISTICAL_ANOMALY",
            "status": "EVALUATED", "explanation": "test",
        }
        bad_severity_row = dict(good_row, id=str(uuid4()), severity="NOT_A_REAL_SEVERITY")
        path = self._write_csv(tmp_path, [good_row, bad_severity_row], fieldnames)

        stats1 = ingest_anomalies(path, TEST_DATABASE_URL)
        assert stats1["inserted"] == 1
        assert stats1["failed"] == 1  # the bad-severity row

        stats2 = ingest_anomalies(path, TEST_DATABASE_URL)
        assert stats2["inserted"] == 0
        assert stats2["skipped_existing"] == 1

        count = db_session.query(WeatherAnomaly).filter(WeatherAnomaly.id == good_row["id"]).count()
        assert count == 1
