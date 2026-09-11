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

## Next Steps

### Phase 5 MVP Demo

1. Register 2-3 users (citizen, analyst, admin roles)
2. Submit report as citizen
3. View event as analyst
4. Check evidence status (verify Phase 3C integration)

### Phase 6 (Admin Workflow)

- Add POST /admin/events/{id}/review endpoint
- Implement admin verification queue
- Add alert engine
- Implement final_verification_status workflow

### Phase 7 (React Frontend)

- Build React + Tailwind UI
- Integrate with Phase 5 API
- Real-time map visualization
- Role-based dashboard views

## Support

For issues or questions:

1. Check troubleshooting section above
2. Review API.md for endpoint documentation
3. Run tests: `pytest backend/tests/ -v`
4. Check logs: `docker-compose logs`
5. Examine database: `docker-compose exec postgres psql ...`
