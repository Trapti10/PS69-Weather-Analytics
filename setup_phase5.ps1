# PS69 Phase 5 - Windows PowerShell setup
#
# IMPORTANT: $ErrorActionPreference = "Stop" only makes PowerShell *cmdlet*
# errors terminating. It does NOT fail the script when a native executable
# (docker, python, pytest, psql) exits with a non-zero code. Every native
# call below is therefore followed by an explicit $LASTEXITCODE check via
# Assert-Success, so a real failure actually stops the script instead of
# being silently passed over.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Assert-Success {
    param([string]$StepName)
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "FAIL: $StepName (exit code $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "=========================================="
Write-Host "PS69 Weather Analytics - Phase 5 Setup (Windows)"
Write-Host "=========================================="

# --- 1. Check prerequisites ---
Write-Host ""
Write-Host "[1/11] Checking prerequisites..."
docker --version | Out-Null
Assert-Success "docker not found"
python --version | Out-Null
Assert-Success "python not found"
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "FAIL: docker-compose.yml not found at $PSScriptRoot" -ForegroundColor Red
    exit 1
}
Write-Host "Prerequisites OK."

# --- Install Python dependencies now (required before schema/migration
# scripts below can import sqlalchemy/psycopg) ---
Write-Host ""
Write-Host "[2/11] Installing Phase 5 Python dependencies..."
python -m pip install -r backend/requirements.txt
Assert-Success "pip install backend/requirements.txt"

# --- 2. Start Docker PostgreSQL/PostGIS ---
Write-Host ""
Write-Host "[3/11] Starting PostgreSQL + PostGIS (Docker)..."
docker compose up -d postgres pgadmin
Assert-Success "docker compose up -d postgres pgadmin"

# --- 3. Wait for DB readiness ---
Write-Host ""
Write-Host "[4/11] Waiting for PostgreSQL to be ready..."
$ready = $false
for ($i = 1; $i -le 30; $i++) {
    docker exec ps69_postgres pg_isready -U ps69_admin -d ps69_weather *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Write-Host "  Waiting for PostgreSQL... ($i/30)"
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Write-Host "FAIL: PostgreSQL did not become ready." -ForegroundColor Red
    docker compose logs postgres
    exit 1
}
Write-Host "PostgreSQL is ready."

# --- 4. Verify PostGIS ---
Write-Host ""
Write-Host "[5/11] Verifying PostGIS extension..."
# Explicitly enable PostGIS before checking its version so this works on a fresh database
# as well as an existing database. This is safe to run repeatedly.
docker exec ps69_postgres psql -v ON_ERROR_STOP=1 -U ps69_admin -d ps69_weather -c "CREATE EXTENSION IF NOT EXISTS postgis;"
Assert-Success "PostGIS extension enablement"
docker exec ps69_postgres psql -U ps69_admin -d ps69_weather -tAc "SELECT postgis_version();"
Assert-Success "PostGIS verification"

# --- 5. Create/load schema ---
Write-Host ""
Write-Host "[6/11] Creating/refreshing database schema..."
Get-Content backend/db/schema.sql | docker exec -i ps69_postgres psql -v ON_ERROR_STOP=1 -U ps69_admin -d ps69_weather
Assert-Success "schema creation"

# --- 6. Run Phase 3A -> PostgreSQL migration ---
Write-Host ""
Write-Host "[7/11] Migrating Phase 3A report data into PostgreSQL..."
# Confirmed on-disk location: data/phase3/processed/all_weather_reports.json
# (this repository has no data/phase3a/ directory).
$JsonFile = Join-Path $PSScriptRoot "data\phase3\processed\all_weather_reports.json"
if (-not (Test-Path $JsonFile)) {
    Write-Host "FAIL: Phase 3A report file not found: $JsonFile" -ForegroundColor Red
    exit 1
}
$env:DATABASE_URL = "postgresql+psycopg://ps69_admin:ps69_password_dev@localhost:5432/ps69_weather"
python backend/db/migrate_from_json.py --input "$JsonFile" --database-url "$env:DATABASE_URL"
Assert-Success "Phase 3A migration"

# --- 7. (Dependencies already installed in step 2; re-verify here in case
#      requirements changed since) ---
Write-Host ""
Write-Host "[8/11] Re-checking Python dependencies..."
python -m pip install -r backend/requirements.txt
Assert-Success "pip install (re-check)"

# --- 8. Run Phase 5 unit tests ---
Write-Host ""
Write-Host "[9/11] Running Phase 5 unit tests (no DB required)..."
python -m pytest backend/tests/test_phase5_unit.py -v
Assert-Success "Phase 5 unit tests"

# --- 9. Run Phase 5 integration tests against real DB ---
Write-Host ""
Write-Host "[10/11] Running Phase 5 integration tests (real PostgreSQL/PostGIS)..."
python -m pytest backend/tests/test_phase5_integration.py -v
Assert-Success "Phase 5 integration tests"

# --- 10. Run Phase 1-4C regression tests ---
Write-Host ""
Write-Host "[11/11] Running Phase 1-4C regression tests..."
python -m pytest tests/ -q
Assert-Success "Phase 1-4C regression tests"

# --- 11. Final summary ---
Write-Host ""
Write-Host "=========================================="
Write-Host "PHASE 5 WINDOWS SETUP: ALL STEPS PASSED"
Write-Host "=========================================="
Write-Host ""
Write-Host "Start the API with:"
Write-Host "  uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload"
