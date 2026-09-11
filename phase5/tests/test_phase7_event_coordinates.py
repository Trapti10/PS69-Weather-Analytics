"""
Phase 7 addition: tests that GET /events and GET /events/{id} expose real
latitude/longitude (extracted from the existing WeatherEvent.location PostGIS
point via ST_X/ST_Y) so the frontend map can plot true coordinates.

Additive only — reuses the same fixture pattern as the other Phase 5/6/7 test
files (dedicated ps69_weather_test database, real PostgreSQL + PostGIS).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from phase5.api.main import app
from phase5.api.db import Base, get_db

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
    session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def _register(client, email, role="CITIZEN", password="TestPassword123!"):
    resp = client.post("/auth/register", json={"email": email, "password": password, "role": "CITIZEN"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    if role == "CITIZEN":
        return token
    # Analyst/Admin accounts aren't publicly registerable; promote directly in DB for the test.
    return token


class TestEventCoordinates:
    def test_event_list_includes_coordinates_when_submitted_with_location(self, client, db_session):
        token = _register(client, "coorduser@test.com")
        submit_resp = client.post(
            "/reports/",
            json={
                "text": "Flooding reported near the river bridge",
                "city": "Jabalpur",
                "state": "Madhya Pradesh",
                "latitude": 23.1815,
                "longitude": 79.9864,
                "event_type": "FLOODING",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert submit_resp.status_code == 201
        event_id = submit_resp.json()["event_id"]
        assert event_id is not None

        # Promote this user to ADMIN directly via the test DB session so they can
        # see the (likely NEEDS_REVIEW) event through GET /events and GET /events/{id}.
        from phase5.api.models import User

        user_obj = db_session.query(User).filter(User.email == "coorduser@test.com").first()
        assert user_obj is not None
        user_obj.role = "ADMIN"
        db_session.add(user_obj)
        db_session.commit()

        # Re-login to get a token carrying the ADMIN role.
        login_resp = client.post(
            "/auth/login", json={"email": "coorduser@test.com", "password": "TestPassword123!"}
        )
        admin_token = login_resp.json()["access_token"]

        detail_resp = client.get(
            f"/events/{event_id}", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["latitude"] is not None
        assert detail["longitude"] is not None
        assert abs(detail["latitude"] - 23.1815) < 0.001
        assert abs(detail["longitude"] - 79.9864) < 0.001

        list_resp = client.get("/events", headers={"Authorization": f"Bearer {admin_token}"})
        assert list_resp.status_code == 200
        events = list_resp.json()["events"]
        matching = [e for e in events if e["event_id"] == event_id]
        assert len(matching) == 1
        assert matching[0]["latitude"] is not None
        assert matching[0]["longitude"] is not None


class TestEventFilters:
    """Phase 7 regression: dashboard filters must map to real backend query parameters."""

    def test_event_type_and_date_filters(self, client, db_session):
        from phase5.api.models import User
        from datetime import datetime, timezone

        token = _register(client, "filteruser@test.com")

        responses = []
        for text_body, city, event_type in [
            ("Heavy rainfall near the market area", "Jabalpur", "RAINFALL"),
            ("Flooding on the main road near the bridge", "Jabalpur", "FLOODING"),
        ]:
            response = client.post(
                "/reports/",
                json={
                    "text": text_body,
                    "city": city,
                    "state": "Madhya Pradesh",
                    "latitude": 23.1815,
                    "longitude": 79.9864,
                    "event_type": event_type,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 201
            responses.append(response.json())

        user_obj = db_session.query(User).filter(User.email == "filteruser@test.com").first()
        assert user_obj is not None
        user_obj.role = "ADMIN"
        db_session.add(user_obj)
        db_session.commit()

        login_resp = client.post(
            "/auth/login",
            json={"email": "filteruser@test.com", "password": "TestPassword123!"},
        )
        admin_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        rainfall = client.get("/events?event_type=RAINFALL", headers=headers)
        assert rainfall.status_code == 200
        rainfall_events = rainfall.json()["events"]
        assert all(event["event_type"] == "RAINFALL" for event in rainfall_events)

        filtered_by_date = client.get(
            "/events?start_date=2000-01-01T00:00:00&end_date=2100-01-01T00:00:00",
            headers=headers,
        )
        assert filtered_by_date.status_code == 200
        assert filtered_by_date.json()["total"] >= 2
