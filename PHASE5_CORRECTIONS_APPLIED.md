# Phase 5 Corrections Applied

This package contains direct corrections to the supplied Phase 5 ZIP.

## Corrected
- Replaced `psycopg2-binary==2.9.9` with `psycopg[binary]==3.2.9` for binary PostgreSQL wheels.
- Standardized SQLAlchemy URLs to `postgresql+psycopg://...`.
- Added root `.env.example`.
- Removed setup dependence on missing `.env.phase5`.
- Removed migration/test error swallowing from setup scripts.
- Kept the repository's actual Phase 3 report path: `data/phase3/processed/all_weather_reports.json`.
- Added a Windows `setup_phase5.ps1` helper.
- Changed integration DB tests so unavailable PostgreSQL is a test failure rather than a silent skip.
- Added automatic creation of the dedicated `ps69_weather_test` database when the configured PostgreSQL user has permission.
- Fixed `/ready` to use SQLAlchemy `text()`.
- Fixed PostGIS distance correlation to cast points to `Geography` so the 10 km threshold is measured in meters.
- Restored the approved 3-hour temporal correlation window.
- Improved event query total counting to respect filters.
- Aligned ORM JSON fields with PostgreSQL JSONB.
- Removed fake seeded password hashes from the SQL schema.
- Restricted public registration to CITIZEN accounts; privileged roles are provisioned outside public registration.
- Preserved the existing Phase 1–4C source files.

## Verification performed in this environment
- All Phase 5 Python files compile successfully.
- Both setup shell scripts pass `bash -n` syntax validation.
- Static invariant checks for PostgreSQL driver, PostGIS URL, migration path, no test skipping, and spatial correlation passed.

## Environment limitation
Docker and external package installation are not available in this execution environment, so a live PostgreSQL/PostGIS/API run could not be performed here. On Windows, run `setup_phase5.ps1` after starting Docker Desktop and confirm the live test counts before declaring Phase 5 complete.
