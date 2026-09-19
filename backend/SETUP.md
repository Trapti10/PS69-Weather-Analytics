# Phase 5 Setup Guide

## Quick Start (5 minutes)

### Prerequisites
- Docker & docker-compose
- Python 3.10+
- PostgreSQL 15 + PostGIS 3.3 (via Docker)

### One-Command Setup

```bash
cd PS69-Weather-Analytics
chmod +x phase5/setup.sh
./backend/setup.sh
```

This script:
1. Verifies dependencies
2. Installs Python packages
3. Starts PostgreSQL + PostGIS in Docker
4. Creates database schema
5. Migrates Phase 3A report data

### Start the API

#### Option A: Direct Python
```bash
cd PS69-Weather-Analytics
python3 -m uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```

#### Option B: Docker Compose
```bash
cd PS69-Weather-Analytics
docker-compose up
```

### Verify Setup

```bash
# Health check
curl http://localhost:8000/health

# API documentation (interactive)
open http://localhost:8000/docs

# pgAdmin (database management)
open http://localhost:5050
# Login: admin@ps69.local / admin
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and adjust:

```bash
# Database
DATABASE_URL=postgresql+psycopg://ps69_admin:ps69_password_dev@localhost:5432/ps69_weather

# JWT
JWT_SECRET=change-this-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# FastAPI
FASTAPI_ENV=development
FASTAPI_DEBUG=true

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# Feature Flags
ENABLE_SOCIAL_FIXTURE_INGESTION=true
ENABLE_ALERT_DELIVERY=true
```

## Detailed Installation

### Step 1: Install Python Dependencies

```bash
cd PS69-Weather-Analytics
pip install -r backend/requirements.txt
```

### Step 2: Start PostgreSQL + PostGIS

```bash
# Using docker-compose (recommended)
docker-compose up -d postgres pgadmin

# Wait for database to be ready
docker-compose exec postgres pg_isready -U ps69_admin -d ps69_weather

# Or start manually
docker run -d \
  --name ps69_postgres \
  -e POSTGRES_DB=ps69_weather \
  -e POSTGRES_USER=ps69_admin \
  -e POSTGRES_PASSWORD=ps69_password_dev \
  -p 5432:5432 \
  postgis/postgis:15-3.3
```

### Step 3: Create Database Schema

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'backend')
from backend.api.db import Base, engine
from backend.api.models import *

# Create all tables
Base.metadata.create_all(bind=engine)
print("✓ Schema created")
EOF
```

### Step 4: Migrate Existing Data (Optional)

```bash
export DATABASE_URL="postgresql+psycopg://ps69_admin:ps69_password_dev@localhost:5432/ps69_weather"

python3 backend/db/migrate_from_json.py \
  --input data/phase3/processed/all_weather_reports.json \
  --database-url "$DATABASE_URL"
```

### Step 4b: Load Weather Intelligence Analytics Data

Populates the Analyst/Admin intelligence dashboards with the real ERA5 +
Open-Meteo + Phase 4C anomaly data already collected by this project (see
"Weather Intelligence Analytics" below for the full architecture):

```bash
python3 -m backend.db.ingest_analytics_data
```

Safe to re-run any time (idempotent - already-loaded rows are skipped).

### Step 5: Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run Phase 5 tests
pytest backend/tests/test_phase5_integration.py -v

# Run existing Phase 1-4C tests (verify nothing broke)
pytest tests/ -v
```

### Step 6: Start FastAPI

```bash
python3 -m uvicorn backend.api.main:app --reload
```

API is now available at `http://localhost:8000`

## Troubleshooting

### PostgreSQL Connection Error

```
ERROR: psycopg2.OperationalError: could not connect to server
```

**Solution:**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Restart if needed
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### Port Already in Use

```
ERROR: Address already in use
```

**Solution:**
```bash
# Change port in uvicorn command
python3 -m uvicorn backend.api.main:app --port 8001

# Or kill existing process
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

### Phase 1-4C Pipeline Not Available

```
WARNING: Phase 1-4C pipeline not available
```

**Means:** Reports will still be processed but without evidence scoring.

**Solution:** Ensure `src/` directory contains Phase 1-4C code:
```bash
ls -la src/corroboration/verification_engine.py
```

### Schema Mismatch

If you get SQLAlchemy/PostgreSQL schema mismatch errors:

```bash
# Drop and recreate
python3 << 'EOF'
import sys
sys.path.insert(0, 'backend')
from backend.api.db import Base, engine

# WARNING: Deletes all data!
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("✓ Schema reset")
EOF
```

## Development Workflow

### Local Development

```bash
# Terminal 1: PostgreSQL
docker-compose up postgres

# Terminal 2: FastAPI (with auto-reload)
python3 -m uvicorn backend.api.main:app --reload

# Terminal 3: Run tests as you code
pytest backend/tests/ -v --tb=short
```

### Adding New Routes

1. Create handler in `backend/api/routes/`
2. Import and include in `backend/api/main.py`
3. Add tests to `backend/tests/`
4. Check documentation in `API.md`

### Database Schema Changes

1. Update `backend/api/models.py`
2. Update `backend/db/schema.sql` if needed
3. Drop and recreate tables (development only!)
4. Run migrations

## Docker Compose Services

### Services Defined

```yaml
postgres:  # PostgreSQL 15 + PostGIS 3.3
  Port: 5432
  Volume: ps69_data (persistent)

pgadmin:   # Database management UI
  Port: 5050
  User: admin@ps69.local / admin

fastapi:   # FastAPI application
  Port: 8000
  Auto-reload on file changes
```

### Useful Docker Compose Commands

```bash
# Start all services
docker-compose up

# Start in background
docker-compose up -d

# Stop services
docker-compose stop

# Stop and remove containers
docker-compose down

# View logs
docker-compose logs -f

# Execute command in container
docker-compose exec postgres psql -U ps69_admin -d ps69_weather
```

## Performance Tuning

### For Local Development

Default settings are fine for development:
- Single PostgreSQL instance
- In-memory connection pool
- Auto-reload FastAPI

### For Production (Future Phases)

```env
# Database pooling
SQLALCHEMY_POOL_SIZE=20
SQLALCHEMY_MAX_OVERFLOW=40

# JWT
JWT_SECRET=<strong-random-value>

# Logging
LOG_LEVEL=INFO

# Disable debug
FASTAPI_DEBUG=false

# Add CORS origins as needed
CORS_ORIGINS=https://yourdomain.com
```

## Monitoring

### API Health

```bash
# Basic health
curl http://localhost:8000/health

# Database readiness
curl http://localhost:8000/ready

# Logs (if using docker)
docker-compose logs -f fastapi
```

### Database Monitoring

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U ps69_admin -d ps69_weather

# Check table sizes
SELECT 
  tablename, 
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname='public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

# Check active connections
SELECT 
  datname, 
  usename, 
  pid, 
  query 
FROM pg_stat_activity;
```

## Weather Intelligence Analytics

The Analyst and Admin dashboards are backed by two additional tables -
`weather_observations` and `weather_anomalies` - populated from the real
datasets this project already collected, cleaned, fused, and analyzed in
Phases 1-4C. This is deliberately separate from the citizen-report/
verification pipeline (`weather_reports`/`weather_events`): those are the
Phase 3-6 pipeline, this is the raw scientific observation record.

### Where the data comes from

| Source dataset | Destination table | Real row count |
|---|---|---|
| `data/phase2/fused/era5_weather_records.csv` (source=ERA5) | `weather_observations` | 17,544 |
| `data/phase2c/fused/openmeteo_weather_records.csv` (source=Open-Meteo) | `weather_observations` | 17,544 |
| `data/phase4c/anomalies.csv` (Phase 4C rolling z-score / rainfall-ratio detector output - every row is already a flagged anomaly) | `weather_anomalies` | 1,309 |

Both source CSVs were inspected column-by-column before the schema was
designed (see `backend/db/schema.sql` for the full column mapping and
provenance comments on both tables) - no field was invented that isn't in
the source data. `location_name` is left NULL by ingestion: the source
CSVs only carry raw latitude/longitude (this project's ERA5/Open-Meteo data
covers a single station - the same one as `jabalpur_weather_2024_2025.csv` -
but no name for it appears in these particular files), so nothing is
guessed at ingestion time. The column stays in the schema, nullable, for
any future source that does provide a place name; the dashboard/map fall
back to showing raw coordinates when it's NULL.

`weather_anomalies.severity` (LOW/MEDIUM/HIGH/CRITICAL, Phase 4C's own
vocabulary) is intentionally a different set of values from
`weather_events.severity` (LOW/MEDIUM/HIGH/EXTREME) - the two are not the
same concept and are never conflated in the schema, ingestion, or API.

### Loading the data

```bash
# Load everything (idempotent - safe to re-run)
python -m backend.db.ingest_analytics_data

# Or just one half
python -m backend.db.ingest_analytics_data --observations-only
python -m backend.db.ingest_analytics_data --anomalies-only
```

Idempotency works the same way as `migrate_from_json.py`: every source row
already carries a stable id from when Phase 2/4C produced it, so re-running
against the same files after the first successful load is a no-op (every
row reports `skipped_existing`). Malformed rows (unparseable timestamp,
missing id, unrecognized severity) are logged and skipped without failing
the rest of the batch; the script exits non-zero if anything was skipped
this way so it's visible in CI/deploy logs.

### Analytics API

All aggregation (COUNT/AVG/SUM/MIN/MAX/GROUP BY/date_trunc) happens in
PostgreSQL - `backend/api/routes/analytics.py` never loads raw rows into
Python to compute a number, and no endpoint here ever sends raw
observation/anomaly rows to the frontend for client-side math. All
endpoints require ANALYST or ADMIN (same `require_analyst` dependency
`/events` already uses) - there is no citizen-facing analytics endpoint.

| Endpoint | Returns |
|---|---|
| `GET /analytics/overview` | Top-line KPIs: observation/event/report/anomaly/source totals, verification counts, avg/max temperature, total rainfall |
| `GET /analytics/weather-trends` | Day-bucketed avg temperature / rainfall / humidity / wind. Filters: `source`, `start_date`, `end_date` |
| `GET /analytics/rainfall` | Day-bucketed total rainfall + overall total and max-rainfall day. Same filters |
| `GET /analytics/temperature` | Day-bucketed avg/min/max temperature + overall avg/min/max. Same filters |
| `GET /analytics/source-comparison` | Per-source (ERA5 vs Open-Meteo) observation count and averages. Filters: `start_date`, `end_date` |
| `GET /analytics/anomalies` | Counts grouped by variable+severity and by severity, plus the most recent flagged anomalies. Filters: `source`, `variable`, `severity`, `start_date`, `end_date`, `latest_limit` |
| `GET /analytics/event-distribution` | Real `WeatherEvent` counts by `event_type` and `severity`. Filters: `start_date`, `end_date`, `city` |
| `GET /analytics/verification` | `VERIFIED`/`NEEDS_REVIEW`/`REJECTED` counts (`final_verification_status`, kept separate from `evidence_status`). Filters: `start_date`, `end_date` |

Example response (`GET /analytics/overview`):

```json
{
  "total_weather_observations": 35088,
  "total_weather_events": 0,
  "total_reports": 0,
  "total_anomalies": 1309,
  "total_sources": 2,
  "verified_events": 0,
  "needs_review": 0,
  "rejected_events": 0,
  "average_temperature": 25.46,
  "max_temperature": 44.7,
  "total_rainfall": 5855.99,
  "observations_date_range_start": "2024-01-01T00:00:00",
  "observations_date_range_end": "2025-12-31T23:00:00"
}
```

### How the Analyst dashboard uses this

The Analyst dashboard (frontend `src/pages/analyst/AnalystDashboardPage.tsx`
and `src/features/analytics/`) calls these endpoints through TanStack Query
hooks (`useAnalyticsOverview`, `useWeatherTrends`, `useRainfallAnalytics`,
`useTemperatureAnalytics`, `useSourceComparison`, `useAnomalyAnalytics`,
`useEventDistribution`, `useVerificationAnalytics`) and renders them as KPI
cards, Recharts line/bar/pie charts, and the existing Leaflet map - all
read-only, with zero verify/reject controls anywhere in that page tree.

### How the Admin dashboard uses this

Admin reuses the exact same analytics endpoints and hooks as Analyst (no
duplicated aggregation logic) for the weather-intelligence half of its
dashboard, combined with the existing Phase 6 verification-queue widgets for
the operational half (needs-review count, latest queue items). Admin's
verify/reject workflow itself is unchanged by this work.

## Creating test accounts for all three roles

`POST /auth/register` intentionally only ever creates **CITIZEN** accounts —
this is enforced server-side (`UserRegisterRequest.role` is pinned to
`^CITIZEN$` in `backend/api/schemas.py`, and `routes/auth.py` hardcodes
`role="CITIZEN"` regardless of what's sent). This is by design: public
self-registration must not be able to grant itself elevated access.

ANALYST and ADMIN accounts must be provisioned by an operator instead, using:

```bash
# Create an analyst (prompts for a password interactively; never echoed,
# never written to shell history or logs)
python -m backend.db.provision_role_user --email analyst@example.com --role ANALYST

# Create an admin
python -m backend.db.provision_role_user --email admin@example.com --role ADMIN

# Change an existing account's role (e.g. promote a citizen to analyst)
python -m backend.db.provision_role_user --email someone@example.com --role ADMIN --update-existing
```

Run it with the same `DATABASE_URL` (and `JWT_SECRET`, for consistency with
the running API) as the deployed backend. See
`backend/db/provision_role_user.py` for full usage notes. No credentials are
ever hardcoded in source — the script always reads the password interactively
unless `PS69_PROVISION_PASSWORD` is set in the environment for scripted/CI
setup, and never prints or logs it either way.

## End-to-end role smoke test

1. Register a CITIZEN via `POST /auth/register` (or the frontend's
   "Register as a citizen" link) and submit a report — confirm it appears
   under "My Reports" with an evidence status.
2. Provision an ANALYST with the script above, log in, and confirm the
   Analyst dashboard/events/analytics/map pages load real data with no
   verify/reject controls anywhere.
3. Provision an ADMIN with the script above, log in, open the verification
   queue, inspect an event's evidence, and submit a VERIFIED/NEEDS_REVIEW/
   REJECTED decision — confirm it persists (`AdminReviewAction` + `AuditLog`
   rows written) and that the event's evidence status is untouched by it.
4. Confirm a CITIZEN token gets 403 on `/admin/*` and that an ANALYST token
   gets 403 on `/admin/events/{id}/verify` (both already covered by
   `backend/tests/test_phase6_admin_verification.py::TestAdminAuthorization`).
- Real-time map visualization
- Role-based dashboard views

## Support

For issues or questions:

1. Check troubleshooting section above
2. Review API.md for endpoint documentation
3. Run tests: `pytest backend/tests/ -v`
4. Check logs: `docker-compose logs`
5. Examine database: `docker-compose exec postgres psql ...`

## Weather Intelligence Dashboard Data

The Analyst/Researcher and Administrator workspaces are backed by PostgreSQL/PostGIS analytics rather than browser-side CSV parsing. After the database is running, load the real historical intelligence dataset once with:

```bash
python -m backend.db.ingest_analytics_data
```

The ingestion is idempotent and safe to re-run. The application exposes aggregated analytics under `/analytics/*`, location summaries under `/locations/*`, and a whitelisted Research Data catalog/download API under `/research/artifacts/*`.

The shipped historical scientific dataset is centered on Jabalpur for 2024–2025. The UI surfaces that coverage explicitly rather than implying unsupported national historical coverage.

Key analytical sources surfaced in the product include cleaned observations, ERA5/Open-Meteo source comparison and fusion outputs, corroboration summaries, weather intelligence records, anomaly analysis, forecast/model metrics, and the existing PostgreSQL weather-event verification pipeline.
