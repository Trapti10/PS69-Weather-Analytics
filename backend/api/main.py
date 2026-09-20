"""
National Weather Intelligence Platform
FastAPI Application Entry Point

Synchronous processing model:
- POST /reports: FastAPI endpoint processes request through Phase 1-4C pipeline synchronously
- All processing happens within the request/response cycle
- Response returns after data is written to PostgreSQL
- Latency: ~1-3 seconds per report

No async queue, no background workers, no message broker in MVP.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import logging
import os
from datetime import datetime

# Import routes
from backend.api.routes import auth, reports, events

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ORM metadata uses IF NOT EXISTS semantics through create_all for new
    # tables, so a deployment with an existing PostgreSQL volume can add the
    # current analytics tables without destroying existing data.
    try:
        from backend.api.db import create_tables
        create_tables()
        logger.info("Database schema verified on application startup")
    except Exception as exc:
        logger.error("Database schema verification failed during startup: %s", exc)
    yield


# Create FastAPI app
app = FastAPI(
    title="National Weather Intelligence Platform",
    description="Scalable weather intelligence, analytics, corroboration, anomaly detection and event verification for India.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:8000"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming requests and outgoing responses."""
    start_time = datetime.now()
    
    # Process request
    response = await call_next(request)
    
    # Calculate latency
    process_time = (datetime.now() - start_time).total_seconds()
    
    # Log
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Latency: {process_time:.3f}s"
    )
    
    # Add latency header
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

# Health check
@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }

# Ready check (includes DB connectivity)
@app.get("/ready")
def readiness_check():
    """Readiness check - verifies database connectivity."""
    try:
        from backend.api.db import SessionLocal
        db = SessionLocal()
        # Simple query to verify connectivity
        db.execute(text("SELECT 1"))
        db.close()
        return {
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Database connectivity check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "error": str(e),
            },
        )

# Try to include routers, handle import errors gracefully
try:
    from backend.api.routes import auth, reports, events, admin, analytics, research, locations
    app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
    app.include_router(reports.router, prefix="/reports", tags=["Reports"])
    app.include_router(events.router, prefix="/events", tags=["Events"])
    app.include_router(admin.router, prefix="/admin", tags=["Admin - Phase 6 Verification Workflow"])
    app.include_router(analytics.router, prefix="/analytics", tags=["Analytics - Weather Intelligence"])
    app.include_router(research.router, prefix="/research", tags=["Research Data"])
    app.include_router(locations.router, prefix="/locations", tags=["Locations"])
    logger.info("Routes imported successfully")
except ImportError as e:
    logger.warning(f"Error importing routes: {e}")

# Root endpoint
@app.get("/")
def root():
    """Root endpoint - API information."""
    return {
        "app": "National Weather Intelligence Platform",
        "processing_model": "Synchronous MVP processing",
        "database": "PostgreSQL + PostGIS",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "ready": "/ready",
        },
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.main:app",
        host=os.getenv("FASTAPI_HOST", "0.0.0.0"),
        port=int(os.getenv("FASTAPI_PORT", 8000)),
        reload=os.getenv("FASTAPI_ENV", "development") == "development",
    )
