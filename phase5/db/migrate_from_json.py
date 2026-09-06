"""
Phase 5: Migration from JSON to PostgreSQL

Loads existing Phase 3A weather reports from JSON file into PostgreSQL database.

Handles:
- Reading JSON fixture data
- Normalizing field names
- Validating coordinates
- Creating SQLAlchemy ORM records
- Committing to database

Usage:
    python phase5/db/migrate_from_json.py \
        --input data/phase3/processed/all_weather_reports.json \
        --database-url postgresql+psycopg://user:pass@localhost/ps69_weather
"""

import json
import sys
import logging
from pathlib import Path
from datetime import datetime
from uuid import UUID
import argparse

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add src to path.
# migrate_from_json.py lives at <REPO_ROOT>/phase5/db/migrate_from_json.py,
# so parents[2] is <REPO_ROOT> itself. (A previous version of this script
# used parents[2].parent, which pointed one directory ABOVE the actual repo
# root and made "python phase5/db/migrate_from_json.py ..." -- the exact
# usage documented above -- fail with ModuleNotFoundError unless the caller
# happened to already have the repo root on PYTHONPATH.)
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from phase5.api.db import Base
from phase5.api.models import WeatherReport


def validate_coordinates(lat, lon):
    """Validate latitude and longitude."""
    if lat is None or lon is None:
        return False
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        return -90 <= lat_f <= 90 and -180 <= lon_f <= 180
    except (ValueError, TypeError):
        return False


def parse_timestamp(ts_str):
    """Parse timestamp from string."""
    if not ts_str:
        return None
    try:
        if isinstance(ts_str, str):
            # Handle ISO format with Z or +00:00
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            return datetime.fromisoformat(ts_str)
        return ts_str
    except Exception as e:
        logger.warning(f"Could not parse timestamp {ts_str}: {e}")
        return None


def migrate_reports(json_path: str, database_url: str):
    """
    Migrate weather reports from JSON to PostgreSQL.
    
    Args:
        json_path: Path to JSON file with weather reports
        database_url: PostgreSQL database URL
    
    Returns:
        dict: Migration statistics (read, success, skip, fail)
    """
    # Create database engine
    engine = create_engine(database_url, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    stats = {
        "read": 0,
        "success": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
    }
    
    try:
        # Read JSON file
        logger.info(f"Reading JSON file: {json_path}")
        with open(json_path, "r") as f:
            reports_data = json.load(f)
        
        if not isinstance(reports_data, list):
            logger.error("JSON file does not contain a list of reports")
            stats["failed"] = 1
            return stats
        
        logger.info(f"Found {len(reports_data)} reports in JSON")
        
        # Migrate each report
        for idx, report_dict in enumerate(reports_data):
            stats["read"] += 1
            
            try:
                # Extract fields
                report_id = report_dict.get("report_id")
                if not report_id:
                    logger.warning(f"Record {idx} missing report_id, skipping")
                    stats["skipped"] += 1
                    continue
                
                # Check if already migrated
                existing = session.query(WeatherReport).filter(
                    WeatherReport.report_id == report_id
                ).first()
                if existing:
                    logger.debug(f"Report {report_id} already exists, skipping")
                    stats["skipped"] += 1
                    continue
                
                # Build record
                latitude = report_dict.get("latitude")
                longitude = report_dict.get("longitude")
                
                location = None
                if validate_coordinates(latitude, longitude):
                    # PostGIS format: SRID=4326;POINT(lon lat)
                    location = f"SRID=4326;POINT({longitude} {latitude})"
                
                report_timestamp = parse_timestamp(
                    report_dict.get("timestamp")
                )
                ingestion_timestamp = parse_timestamp(
                    report_dict.get("ingestion_timestamp")
                )
                if not ingestion_timestamp:
                    ingestion_timestamp = datetime.utcnow()
                
                # Create ORM record
                weather_report = WeatherReport(
                    report_id=report_id,
                    source_type=report_dict.get("source_type", "UNKNOWN"),
                    source_name=report_dict.get("source_name", "unknown-source"),
                    author_id_or_hash=report_dict.get("author_id_or_hash"),
                    report_timestamp=report_timestamp,
                    ingestion_timestamp=ingestion_timestamp,
                    city=report_dict.get("city"),
                    state=report_dict.get("state"),
                    location=location,
                    text=report_dict.get("text"),
                    image_url=report_dict.get("image_url"),
                    video_url=report_dict.get("video_url"),
                    event_type=report_dict.get("event_type", "OTHER"),
                    raw_event_type=report_dict.get("raw_event_type"),
                    verification_status=report_dict.get("verification_status", "UNVERIFIED"),
                    source_reliability=report_dict.get("source_reliability"),
                    is_duplicate=report_dict.get("is_duplicate", False),
                    duplicate_hash=report_dict.get("duplicate_hash"),
                    is_suspicious=report_dict.get("is_suspicious", False),
                    # Phase 3B fields
                    semantic_similarity_score=report_dict.get("semantic_similarity_score"),
                    predicted_event_category=report_dict.get("predicted_event_category"),
                    event_classification_confidence=report_dict.get("event_classification_confidence"),
                    risk_score=report_dict.get("risk_score"),
                    risk_label=report_dict.get("risk_label"),
                    # Raw payload
                    raw_payload=report_dict,
                )
                
                session.add(weather_report)
                stats["success"] += 1
                
                if stats["success"] % 10 == 0:
                    logger.info(f"Migrated {stats['success']} records...")
            
            except Exception as e:
                logger.error(f"Error migrating record {idx}: {e}")
                stats["failed"] += 1
                stats["errors"].append({
                    "index": idx,
                    "report_id": report_dict.get("report_id"),
                    "error": str(e),
                })
        
        # Commit all changes
        logger.info("Committing changes to database...")
        session.commit()
        logger.info("Migration complete!")
        
        # Print statistics
        logger.info(f"Migration Statistics:")
        logger.info(f"  Read:     {stats['read']}")
        logger.info(f"  Success:  {stats['success']}")
        logger.info(f"  Skipped:  {stats['skipped']}")
        logger.info(f"  Failed:   {stats['failed']}")
        
        if stats["errors"]:
            logger.warning(f"Errors encountered:")
            for error in stats["errors"][:5]:  # Show first 5
                logger.warning(f"  Record {error['index']} ({error['report_id']}): {error['error']}")
        
        return stats
    
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        stats["failed"] = 1
        session.rollback()
        return stats
    
    finally:
        session.close()


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate weather reports from JSON to PostgreSQL"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to JSON file with weather reports",
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="PostgreSQL database URL",
    )
    
    args = parser.parse_args()
    
    # Check input file exists
    if not Path(args.input).exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)
    
    # Run migration
    stats = migrate_reports(args.input, args.database_url)
    
    # Exit with appropriate code
    if stats["failed"] > 0:
        logger.warning(f"Migration completed with {stats['failed']} errors")
        sys.exit(1)
    else:
        logger.info("Migration completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
