"""
Phase 7 addition: tests for GET /reports/me (the "My Reports" endpoint).

This file is additive — it does not modify any existing Phase 5/6 test file.
It reuses the same test_db / db_session / client fixture pattern already
established in test_phase5_integration.py (dedicated ps69_weather_test
database, real PostgreSQL + PostGIS, no mocks).
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


def _register(client, email, password="TestPassword123!"):
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "role": "CITIZEN"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _submit_report(client, token, text_body="Heavy rain reported", city="Jabalpur", event_type="RAINFALL"):
    resp = client.post(
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
    assert resp.status_code == 201
    return resp.json()


class TestMyReportsEndpoint:
    """GET /reports/me — additive Phase 7 endpoint."""

    def test_requires_auth(self, client):
        response = client.get("/reports/me")
        assert response.status_code == 401

    def test_empty_for_new_user(self, client):
        token = _register(client, "newcitizen@test.com")
        response = client.get("/reports/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["reports"] == []
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_returns_only_own_reports(self, client):
        token_a = _register(client, "usera@test.com")
        token_b = _register(client, "userb@test.com")

        _submit_report(client, token_a, text_body="User A's first report")
        _submit_report(client, token_a, text_body="User A's second report")
        _submit_report(client, token_b, text_body="User B's report")

        response_a = client.get("/reports/me", headers={"Authorization": f"Bearer {token_a}"})
        assert response_a.status_code == 200
        data_a = response_a.json()
        assert data_a["total"] == 2
        assert len(data_a["reports"]) == 2
        for r in data_a["reports"]:
            assert "User A" in r["text"]

        response_b = client.get("/reports/me", headers={"Authorization": f"Bearer {token_b}"})
        data_b = response_b.json()
        assert data_b["total"] == 1
        assert "User B" in data_b["reports"][0]["text"]

    def test_newest_first_ordering(self, client):
        token = _register(client, "orderuser@test.com")
        first = _submit_report(client, token, text_body="First report submitted")
        second = _submit_report(client, token, text_body="Second report submitted")

        response = client.get("/reports/me", headers={"Authorization": f"Bearer {token}"})
        data = response.json()
        assert data["total"] == 2
        assert data["reports"][0]["report_id"] == second["report_id"]
        assert data["reports"][1]["report_id"] == first["report_id"]

    def test_pagination(self, client):
        token = _register(client, "paginateuser@test.com")
        for i in range(5):
            _submit_report(client, token, text_body=f"Report number {i}")

        page1 = client.get(
            "/reports/me?limit=2&offset=0", headers={"Authorization": f"Bearer {token}"}
        ).json()
        page2 = client.get(
            "/reports/me?limit=2&offset=2", headers={"Authorization": f"Bearer {token}"}
        ).json()

        assert page1["total"] == 5
        assert len(page1["reports"]) == 2
        assert len(page2["reports"]) == 2
        page1_ids = {r["report_id"] for r in page1["reports"]}
        page2_ids = {r["report_id"] for r in page2["reports"]}
        assert page1_ids.isdisjoint(page2_ids)

    def test_response_includes_evidence_fields(self, client):
        token = _register(client, "evidenceuser@test.com")
        submitted = _submit_report(client, token)

        data = client.get("/reports/me", headers={"Authorization": f"Bearer {token}"}).json()
        item = data["reports"][0]
        assert item["report_id"] == submitted["report_id"]
        assert item["evidence_status"] in {
            "SUPPORTED",
            "CONFLICTING",
            "UNVERIFIED",
            "INSUFFICIENT_EVIDENCE",
            None,
        }
        assert "verification_status" in item
        assert "final_verification_status" in item
        assert "created_at" in item
