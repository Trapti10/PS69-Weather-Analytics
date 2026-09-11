"""
PS69 Weather Analytics - Phase 5: Database Connection
SQLAlchemy setup with PostgreSQL + PostGIS
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import QueuePool
import logging

from backend.api.config import get_database_url, get_settings

logger = logging.getLogger(__name__)

# Get database URL from settings
DATABASE_URL = get_database_url()

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=get_settings().SQLALCHEMY_ECHO,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Verify connections before using
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative base for ORM models
Base = declarative_base()


@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Enable PostGIS/UUID extensions on connection.

    IMPORTANT: these CREATE EXTENSION statements run inside an implicit
    transaction on the raw DBAPI connection. If any statement fails, the
    connection is left in an "aborted transaction" state. Previously the
    except block only logged a warning and left the connection in that
    aborted state, so every query run later on that pooled connection
    failed with database transaction errors -- even though the
    failure looked like a harmless startup warning. We must roll back
    (or commit) explicitly so the connection is usable afterward.
    """
    cursor = dbapi_conn.cursor()
    try:
        # Enable PostGIS extension
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        # Enable UUID extension (must be double-quoted: "uuid-ossp" is not
        # a valid bare SQL identifier because of the hyphen)
        cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        dbapi_conn.commit()
    except Exception as e:
        dbapi_conn.rollback()
        logger.warning(f"Could not enable PostGIS/UUID extensions: {e}")
    finally:
        cursor.close()


def get_db():
    """Dependency: Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_database_connectivity() -> bool:
    """Verify database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connectivity verified")
        return True
    except Exception as e:
        logger.error(f"Database connectivity check failed: {e}")
        return False


def create_tables():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")


def drop_all_tables():
    """Drop all tables (for testing/reset only)."""
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped")
