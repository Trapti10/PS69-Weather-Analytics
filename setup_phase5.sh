#!/bin/bash
set -e

# PS69 Phase 5 Setup Script (Linux/macOS)
# NOTE: phase5/setup.sh is the primary documented entry point (see
# phase5/SETUP.md). This script is a lighter alternate flow kept for
# convenience; it is fixed here so it does not silently skip required
# steps (previously it never ran the Phase 3A migration at all).

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================"
echo "PS69 Phase 5 - Foundation Setup"
echo "========================================"

echo ""
echo "1. Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "ERROR: Docker not found."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found."; exit 1; }
if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found at $PROJECT_DIR"
    exit 1
fi
echo "   Prerequisites OK"

echo ""
echo "2. Installing Python dependencies..."
python3 -m pip install -r phase5/requirements.txt

echo ""
echo "3. Starting PostgreSQL + PostGIS..."
docker compose up -d postgres pgadmin

echo ""
echo "4. Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0
until docker exec ps69_postgres pg_isready -U ps69_admin -d ps69_weather 2>/dev/null || [ $attempt -eq $max_attempts ]
do
    attempt=$((attempt + 1))
    echo "   Attempt $attempt/$max_attempts..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: PostgreSQL failed to start"
    exit 1
fi

echo "   PostgreSQL is ready"

echo ""
echo "5. Verifying PostGIS..."
docker exec ps69_postgres psql -U ps69_admin -d ps69_weather -tAc "SELECT postgis_version();"

echo ""
echo "6. Initializing database schema..."
docker exec ps69_postgres psql -v ON_ERROR_STOP=1 -U ps69_admin -d ps69_weather -f /docker-entrypoint-initdb.d/01-schema.sql

echo ""
echo "7. Migrating Phase 3A report data into PostgreSQL..."
# Confirmed on-disk location: data/phase3/processed/all_weather_reports.json
# (this repository has no data/phase3a/ directory).
JSON_FILE="$PROJECT_DIR/data/phase3/processed/all_weather_reports.json"
if [ ! -f "$JSON_FILE" ]; then
    echo "ERROR: Phase 3A report file not found: $JSON_FILE"
    exit 1
fi
DATABASE_URL="postgresql+psycopg://ps69_admin:ps69_password_dev@localhost:5432/ps69_weather"
python3 phase5/db/migrate_from_json.py --input "$JSON_FILE" --database-url "$DATABASE_URL"

echo ""
echo "8. Running Phase 5 unit tests (no DB required)..."
python3 -m pytest phase5/tests/test_phase5_unit.py -v --tb=short
# No error-swallowing: set -e above means a failing test fails this script.

echo ""
echo "9. Running Phase 5 integration tests (real PostgreSQL/PostGIS)..."
python3 -m pytest phase5/tests/test_phase5_integration.py -v --tb=short

echo ""
echo "10. Running Phase 1-4C regression tests..."
python3 -m pytest tests/ -q

echo ""
echo "========================================"
echo "PHASE 5 SETUP: ALL STEPS PASSED"
echo "========================================"
echo ""
echo "To start the FastAPI server:"
echo "  uvicorn phase5.api.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "To test the API:"
echo "  curl http://localhost:8000/docs"
echo ""
echo "To stop the database:"
echo "  docker compose down"
echo ""
