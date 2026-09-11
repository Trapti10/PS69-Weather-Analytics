#!/bin/bash
# Phase 5 Setup Script
# Initializes PostgreSQL, creates schema, loads data, starts FastAPI

set -e

# Correctly resolve project root: phase5/setup.sh -> phase5 -> project root (one level up)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"

echo "=========================================="
echo "PS69 Weather Analytics - Phase 5 Setup"
echo "=========================================="
echo "Project root: $REPO_ROOT"
echo "Phase 5 dir: $BACKEND_DIR"
echo ""

# Verify critical directories exist
if [ ! -d "$REPO_ROOT/src" ]; then
    echo "ERROR: src/ directory not found at $REPO_ROOT/src"
    exit 1
fi
if [ ! -d "$REPO_ROOT/backend" ]; then
    echo "ERROR: backend/ directory not found at $REPO_ROOT/backend"
    exit 1
fi
if [ ! -f "$REPO_ROOT/docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found at $REPO_ROOT"
    exit 1
fi

echo "✓ Project structure verified"
echo ""

# Check dependencies
echo "[1/6] Checking dependencies..."
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not found. Please install Docker."
    exit 1
fi
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found. Please install Python 3.10+."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# Load .env
echo ""
echo "[2/6] Loading configuration..."
if [ ! -f "$REPO_ROOT/.env" ]; then
    echo "Creating .env from .env.example..."
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
else
    echo ".env already exists"
fi

# Install Python dependencies
echo ""
echo "[3/6] Installing Python dependencies..."
python3 -m pip install -r "$BACKEND_DIR/requirements.txt"

# Start PostgreSQL
echo ""
echo "[4/6] Starting PostgreSQL + PostGIS (Docker)..."
cd "$REPO_ROOT"
if docker compose ps postgres &> /dev/null; then
    echo "PostgreSQL already running"
else
    echo "Starting PostgreSQL..."
    docker compose up -d postgres pgadmin
    echo "Waiting for PostgreSQL to be ready..."
    sleep 5
    
    # Wait for database to be ready
    MAX_RETRIES=30
    RETRY_COUNT=0
    while ! docker compose exec -T postgres pg_isready -U ps69_admin -d ps69_weather &> /dev/null; do
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "ERROR: PostgreSQL did not start in time"
            docker compose logs postgres
            exit 1
        fi
        echo "Waiting for PostgreSQL... ($((RETRY_COUNT+1))/$MAX_RETRIES)"
        sleep 1
        RETRY_COUNT=$((RETRY_COUNT+1))
    done
    echo "PostgreSQL is ready!"
fi

# Load schema and migrate data
echo ""
echo "[5/6] Loading database schema and migrating data..."

# Export DATABASE_URL for migration script
export DATABASE_URL="postgresql+psycopg://ps69_admin:ps69_password_dev@localhost:5432/ps69_weather"

# Create schema
echo "Creating database tables..."
python3 -c "
import sys
sys.path.insert(0, '$REPO_ROOT/backend')
sys.path.insert(0, '$REPO_ROOT/src')

from backend.api.db import engine, Base
from backend.api.models import *

# Create all tables
Base.metadata.create_all(bind=engine)
print('✓ Database schema created')
"

# Migrate existing Phase 3A data.
# NOTE: the repository's confirmed on-disk location for the migrated Phase 3A
# report file is data/phase3/processed/all_weather_reports.json (there is no
# data/phase3a/ directory in this repo). This path was verified against the
# actual repository contents before being kept as-is.
JSON_FILE="$REPO_ROOT/data/phase3/processed/all_weather_reports.json"

if [ ! -f "$JSON_FILE" ]; then
    echo "ERROR: Phase 3A report file not found: $JSON_FILE"
    exit 1
fi

echo "Migrating Phase 3A report data..."
python3 "$BACKEND_DIR/db/migrate_from_json.py" \
    --input "$JSON_FILE" \
    --database-url "$DATABASE_URL"

# Verify database
echo ""
echo "Verifying database connectivity..."
python3 -c "
import sys
sys.path.insert(0, '$REPO_ROOT/backend')

from backend.api.db import verify_database_connectivity
if verify_database_connectivity():
    print('✓ Database verified')
else:
    print('ERROR: Database connectivity check failed')
    sys.exit(1)
"

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Start the FastAPI server:"
echo "   cd $REPO_ROOT"
echo "   python3 -m uvicorn backend.api.main:app --reload"
echo ""
echo "2. Or use docker-compose:"
echo "   docker compose up"
echo ""
echo "3. Access the API:"
echo "   API:        http://localhost:8000"
echo "   Docs:       http://localhost:8000/docs"
echo "   ReDoc:      http://localhost:8000/redoc"
echo "   pgAdmin:    http://localhost:5050"
echo ""
echo "4. Run tests:"
echo "   pytest backend/tests/test_phase5_integration.py -v"
echo ""
