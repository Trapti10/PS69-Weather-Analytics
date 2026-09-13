#!/usr/bin/env python3
"""
PS69 Weather Analytics - Operator utility: provision an ANALYST or ADMIN user.

Public self-registration (POST /auth/register) intentionally only ever
creates CITIZEN accounts (see backend/api/schemas.py UserRegisterRequest.role
and backend/api/routes/auth.py:register) — this is enforced server-side by
RBAC, not something the frontend can work around. ANALYST and ADMIN accounts
must be provisioned out-of-band by an operator, which is what this script is
for.

This does NOT hardcode any credentials. Email is passed as a CLI argument;
the password is always read interactively (getpass, never echoed, never
logged, never written to shell history) unless PS69_PROVISION_PASSWORD is
set in the environment (useful for CI/scripted setup, e.g. seeding a fresh
test database) - it is never printed back.

Usage:
    # Create a new analyst
    python -m backend.db.provision_role_user --email analyst@example.com --role ANALYST

    # Create a new admin
    python -m backend.db.provision_role_user --email admin@example.com --role ADMIN

    # Promote/demote an existing user's role instead of creating one
    python -m backend.db.provision_role_user --email someone@example.com --role ADMIN --update-existing

Requires DATABASE_URL (or the individual DB_* / component settings already
used by backend/api/config.py) to be set, same as running the API itself.
"""

import argparse
import getpass
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select

from backend.api.db import SessionLocal
from backend.api.models import User
from backend.api.auth.jwt_handler import JWTHandler

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

VALID_ROLES = {"ANALYST", "ADMIN"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True, help="Email address for the account")
    parser.add_argument("--role", required=True, choices=sorted(VALID_ROLES), help="Role to assign")
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="If the email already exists, update its role (and password, if provided) instead of failing.",
    )
    args = parser.parse_args()

    password = os.getenv("PS69_PROVISION_PASSWORD")
    if not password:
        password = getpass.getpass(f"Password for {args.email}: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            logger.error("Passwords did not match. Aborting.")
            return 1

    if len(password) < 8:
        logger.error("Password must be at least 8 characters (same rule as /auth/register).")
        return 1

    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.email == args.email)).scalars().first()

        if existing and not args.update_existing:
            logger.error(
                f"A user with email {args.email} already exists (role={existing.role}). "
                "Pass --update-existing to change its role/password instead."
            )
            return 1

        hashed = JWTHandler.hash_password(password)

        if existing:
            existing.role = args.role
            existing.password_hash = hashed
            db.commit()
            logger.info(f"Updated {args.email} -> role={args.role}")
        else:
            new_user = User(email=args.email, password_hash=hashed, role=args.role)
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            logger.info(f"Created {args.email} -> role={args.role} (user_id={new_user.user_id})")

        return 0
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to provision user: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
