"""
Login role-selection tests (backend/api/routes/auth.py:login).

The frontend's required "Login as" dropdown sends an optional `role` field
on POST /auth/login. This never grants a role - it only rejects login when
the selected role disagrees with the account's actual, database-backed
role. Fixtures mirror the test_db/db_session/client pattern used throughout
this test suite (see test_phase6_admin_verification.py), defined locally.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.api.main import app
from backend.api.db import Base, get_db
from backend.api.models import User
from backend.api.auth.jwt_handler import JWTHandler

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
    session.rollback()
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


PASSWORD = "TestPassword123!"


def _make_user(db_session, email: str, role: str) -> User:
    user = User(email=email, password_hash=JWTHandler.hash_password(PASSWORD), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ============================================================================
# All 7 required combinations from the spec
# ============================================================================

class TestLoginRoleSelectionMatrix:

    def test_citizen_account_citizen_selected_succeeds(self, client, db_session):
        _make_user(db_session, "citizen1@test.com", "CITIZEN")
        response = client.post(
            "/auth/login", json={"email": "citizen1@test.com", "password": PASSWORD, "role": "CITIZEN"}
        )
        assert response.status_code == 200
        assert response.json()["role"] == "CITIZEN"

    def test_analyst_account_analyst_selected_succeeds(self, client, db_session):
        _make_user(db_session, "analyst1@test.com", "ANALYST")
        response = client.post(
            "/auth/login", json={"email": "analyst1@test.com", "password": PASSWORD, "role": "ANALYST"}
        )
        assert response.status_code == 200
        assert response.json()["role"] == "ANALYST"

    def test_admin_account_admin_selected_succeeds(self, client, db_session):
        _make_user(db_session, "admin1@test.com", "ADMIN")
        response = client.post(
            "/auth/login", json={"email": "admin1@test.com", "password": PASSWORD, "role": "ADMIN"}
        )
        assert response.status_code == 200
        assert response.json()["role"] == "ADMIN"

    def test_citizen_account_admin_selected_rejected(self, client, db_session):
        _make_user(db_session, "citizen2@test.com", "CITIZEN")
        response = client.post(
            "/auth/login", json={"email": "citizen2@test.com", "password": PASSWORD, "role": "ADMIN"}
        )
        assert response.status_code == 403
        assert "different role" in response.json()["detail"]

    def test_citizen_account_analyst_selected_rejected(self, client, db_session):
        _make_user(db_session, "citizen3@test.com", "CITIZEN")
        response = client.post(
            "/auth/login", json={"email": "citizen3@test.com", "password": PASSWORD, "role": "ANALYST"}
        )
        assert response.status_code == 403

    def test_analyst_account_admin_selected_rejected(self, client, db_session):
        _make_user(db_session, "analyst2@test.com", "ANALYST")
        response = client.post(
            "/auth/login", json={"email": "analyst2@test.com", "password": PASSWORD, "role": "ADMIN"}
        )
        assert response.status_code == 403

    def test_admin_account_citizen_selected_rejected(self, client, db_session):
        _make_user(db_session, "admin2@test.com", "ADMIN")
        response = client.post(
            "/auth/login", json={"email": "admin2@test.com", "password": PASSWORD, "role": "CITIZEN"}
        )
        assert response.status_code == 403


# ============================================================================
# The selected role must never leak into the issued token / grant access
# ============================================================================

class TestSelectedRoleNeverGrantsAccess:

    def test_matching_role_login_still_encodes_the_accounts_real_role(self, client, db_session):
        """Sanity check that success isn't just 'role ignored' - the
        returned/encoded role is always user.role, selected role included
        only as a gate, never as the source of the JWT claim."""
        _make_user(db_session, "citizen4@test.com", "CITIZEN")
        response = client.post(
            "/auth/login", json={"email": "citizen4@test.com", "password": PASSWORD, "role": "CITIZEN"}
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        payload = JWTHandler.verify_token(token)
        assert payload["role"] == "CITIZEN"

    def test_citizen_selecting_admin_receives_no_token_and_no_admin_access(self, client, db_session):
        _make_user(db_session, "citizen5@test.com", "CITIZEN")
        response = client.post(
            "/auth/login", json={"email": "citizen5@test.com", "password": PASSWORD, "role": "ADMIN"}
        )
        assert response.status_code == 403
        assert "access_token" not in response.json()

        # Confirm there is no way to then use this rejected response against an admin endpoint.
        admin_check = client.get(
            "/admin/verification-queue", headers={"Authorization": "Bearer whatever-was-not-issued"}
        )
        assert admin_check.status_code == 401


# ============================================================================
# Backward compatibility: role is optional, existing callers unaffected
# ============================================================================

class TestLoginRoleOptional:

    def test_login_without_role_field_still_works_exactly_as_before(self, client, db_session):
        _make_user(db_session, "legacy1@test.com", "CITIZEN")
        response = client.post("/auth/login", json={"email": "legacy1@test.com", "password": PASSWORD})
        assert response.status_code == 200
        assert response.json()["role"] == "CITIZEN"

    def test_login_without_role_field_works_for_analyst_too(self, client, db_session):
        _make_user(db_session, "legacy2@test.com", "ANALYST")
        response = client.post("/auth/login", json={"email": "legacy2@test.com", "password": PASSWORD})
        assert response.status_code == 200
        assert response.json()["role"] == "ANALYST"

    def test_wrong_password_still_returns_generic_401_regardless_of_role(self, client, db_session):
        _make_user(db_session, "wrongpw@test.com", "CITIZEN")
        response = client.post(
            "/auth/login", json={"email": "wrongpw@test.com", "password": "wrong", "role": "CITIZEN"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_unknown_email_still_returns_generic_401_regardless_of_role(self, client, db_session):
        response = client.post(
            "/auth/login",
            json={"email": "doesnotexist@test.com", "password": PASSWORD, "role": "ADMIN"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_invalid_role_value_is_rejected_as_bad_request(self, client, db_session):
        _make_user(db_session, "badrole@test.com", "CITIZEN")
        response = client.post(
            "/auth/login",
            json={"email": "badrole@test.com", "password": PASSWORD, "role": "SUPERUSER"},
        )
        assert response.status_code == 422  # Pydantic pattern validation, request never reaches the handler
