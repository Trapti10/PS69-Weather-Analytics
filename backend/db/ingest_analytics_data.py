"""
PS69 Weather Analytics - Analytics data ingestion

Loads the repository's REAL, already-collected weather datasets into the
PostgreSQL analytics tables (weather_observations, weather_anomalies) that
back the Analyst/Admin intelligence dashboards.

This does NOT touch the citizen-report/verification pipeline
(weather_reports/weather_events) and does NOT modify any source dataset -
it only reads them.

Source datasets -> destination table:

    data/phase2/fused/era5_weather_records.csv       -> weather_observations (source=ERA5)
    data/phase2c/fused/openmeteo_weather_records.csv -> weather_observations (source=Open-Meteo)
    data/phase4c/anomalies.csv                       -> weather_anomalies

Usage:
    python -m backend.db.ingest_analytics_data
    python -m backend.db.ingest_analytics_data --observations-only
    python -m backend.db.ingest_analytics_data --anomalies-only
    python -m backend.db.ingest_analytics_data --database-url postgresql+psycopg://...
    python -m backend.db.ingest_analytics_data --batch-size 5000

Idempotency (bulk, database-enforced):
    Every source row already carries a stable UUID `id` (generated once
    when these Phase 2/4C outputs were produced, not regenerated per run).
    Rows are loaded in batches as a single multi-row
    `INSERT ... ON CONFLICT (id) DO NOTHING RETURNING id` statement per
    batch - the database itself silently skips any id already present,
    rather than this script issuing one SELECT per row first. Re-running
    this script against the same files is a no-op after the first run.
    Rows are never updated in place; if you need to reload changed source
    data, delete the affected rows first.
"""

import csv
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import argparse

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ingest_analytics_data.py lives at <REPO_ROOT>/backend/db/, so parents[2] is
# <REPO_ROOT> (same convention as migrate_from_json.py in this directory).
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.api.config import get_settings
from backend.api.models import WeatherObservation, WeatherAnomaly

DEFAULT_ERA5_PATH = REPO_ROOT / "data" / "phase2" / "fused" / "era5_weather_records.csv"
DEFAULT_OPENMETEO_PATH = REPO_ROOT / "data" / "phase2c" / "fused" / "openmeteo_weather_records.csv"
DEFAULT_ANOMALIES_PATH = REPO_ROOT / "data" / "phase4c" / "anomalies.csv"

# One multi-row INSERT ... ON CONFLICT DO NOTHING per this many valid rows.
# Large enough to make a real difference over one-row-at-a-time inserts,
# small enough that a single statement/transaction stays reasonable and
# progress is still visible in the logs for a 17k+ row file.
DEFAULT_BATCH_SIZE = 2000

# location_name is intentionally left NULL by this script. The source CSVs
# only carry raw latitude/longitude - no station/place name column - so
# ingestion does not derive or guess one. The `weather_observations` /
# `weather_anomalies` schema still has a nullable location_name column for
# any future source that does provide one; consumers (API, frontend) should
# fall back to displaying raw coordinates when it is NULL.


def _parse_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as e:
        logger.warning(f"Could not parse timestamp {value!r}: {e}")
        return None


def _point_wkt(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
    if lat is None or lon is None:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return f"SRID=4326;POINT({lon} {lat})"


def _bulk_upsert_batch(session, table, rows: list[dict]) -> int:
    """INSERT a batch of row-dicts with ON CONFLICT (id) DO NOTHING.

    Returns the number of rows actually inserted (rows whose id already
    existed are silently skipped by Postgres and are not returned by
    RETURNING id, so `len(batch) - inserted` is exactly the skip count).
    """
    if not rows:
        return 0
    stmt = pg_insert(table).values(rows).on_conflict_do_nothing(index_elements=["id"]).returning(table.c.id)
    result = session.execute(stmt)
    inserted = len(result.fetchall())
    session.commit()
    return inserted


def ingest_observations(csv_path: Path, database_url: str, batch_size: int = DEFAULT_BATCH_SIZE) -> dict:
    """Load one Phase 2/2C fused observation CSV into weather_observations.

    Row-level parsing/validation (missing id, unparseable timestamp) still
    happens per row before a row is added to a batch. The actual database
    write is bulk: one INSERT ... ON CONFLICT DO NOTHING per `batch_size`
    valid rows, not one SELECT-then-INSERT per row.
    """
    engine = create_engine(database_url, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    stats = {"read": 0, "inserted": 0, "skipped_existing": 0, "failed": 0, "errors": []}
    required_columns = {"id", "source", "timestamp", "latitude", "longitude"}
    table = WeatherObservation.__table__

    try:
        logger.info(f"Reading observations from {csv_path} (batch size {batch_size})")
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or not required_columns.issubset(set(reader.fieldnames)):
                missing = required_columns - set(reader.fieldnames or [])
                raise ValueError(f"{csv_path} is missing required columns: {missing}")

            batch: list[dict] = []

            def flush():
                if not batch:
                    return
                inserted = _bulk_upsert_batch(session, table, batch)
                stats["inserted"] += inserted
                stats["skipped_existing"] += len(batch) - inserted
                logger.info(
                    f"  ...batch of {len(batch)} processed "
                    f"({stats['inserted']} inserted, {stats['skipped_existing']} already existed so far)"
                )
                batch.clear()

            for idx, row in enumerate(reader):
                stats["read"] += 1
                try:
                    row_id = row.get("id")
                    if not row_id:
                        logger.warning(f"Row {idx} in {csv_path.name} has no id, skipping")
                        stats["failed"] += 1
                        continue

                    observed_at = _parse_timestamp(row.get("timestamp"))
                    if observed_at is None:
                        logger.warning(f"Row {idx} in {csv_path.name} has an unparseable timestamp, skipping")
                        stats["failed"] += 1
                        continue

                    lat = _parse_float(row.get("latitude"))
                    lon = _parse_float(row.get("longitude"))

                    batch.append(
                        dict(
                            id=row_id,
                            source=row.get("source", "UNKNOWN"),
                            observed_at=observed_at,
                            latitude=lat,
                            longitude=lon,
                            location_name=None,  # not present in source data, see note above
                            temperature=_parse_float(row.get("temperature")),
                            humidity=_parse_float(row.get("humidity")),
                            rainfall=_parse_float(row.get("rainfall")),
                            wind_speed=_parse_float(row.get("wind_speed")),
                            wind_direction=_parse_float(row.get("wind_direction")),
                            pressure=_parse_float(row.get("pressure")),
                            verification_status=row.get("verification_status") or None,
                            confidence_score=_parse_float(row.get("confidence_score")),
                            quality_flags=row.get("quality_flags") or None,
                            location=_point_wkt(lat, lon),
                        )
                    )

                    if len(batch) >= batch_size:
                        flush()

                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append({"index": idx, "error": str(e)})
                    logger.error(f"Row {idx} in {csv_path.name} failed: {e}")

            flush()  # final partial batch

        logger.info(
            f"{csv_path.name}: read={stats['read']} inserted={stats['inserted']} "
            f"skipped_existing={stats['skipped_existing']} failed={stats['failed']}"
        )
        return stats
    except Exception as e:
        session.rollback()
        logger.error(f"Ingestion of {csv_path} failed: {e}", exc_info=True)
        stats["failed"] += 1
        stats["errors"].append({"index": None, "error": str(e)})
        return stats
    finally:
        session.close()


def ingest_anomalies(csv_path: Path, database_url: str, batch_size: int = DEFAULT_BATCH_SIZE) -> dict:
    """Load the Phase 4C flagged-anomaly CSV into weather_anomalies.

    Same bulk INSERT ... ON CONFLICT DO NOTHING approach as
    ingest_observations() - see its docstring.
    """
    engine = create_engine(database_url, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    stats = {"read": 0, "inserted": 0, "skipped_existing": 0, "failed": 0, "errors": []}
    required_columns = {"id", "source", "timestamp", "variable", "severity"}
    valid_severities = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    table = WeatherAnomaly.__table__

    try:
        logger.info(f"Reading anomalies from {csv_path} (batch size {batch_size})")
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or not required_columns.issubset(set(reader.fieldnames)):
                missing = required_columns - set(reader.fieldnames or [])
                raise ValueError(f"{csv_path} is missing required columns: {missing}")

            batch: list[dict] = []

            def flush():
                if not batch:
                    return
                inserted = _bulk_upsert_batch(session, table, batch)
                stats["inserted"] += inserted
                stats["skipped_existing"] += len(batch) - inserted
                logger.info(
                    f"  ...batch of {len(batch)} processed "
                    f"({stats['inserted']} inserted, {stats['skipped_existing']} already existed so far)"
                )
                batch.clear()

            for idx, row in enumerate(reader):
                stats["read"] += 1
                try:
                    row_id = row.get("id")
                    if not row_id:
                        logger.warning(f"Row {idx} in {csv_path.name} has no id, skipping")
                        stats["failed"] += 1
                        continue

                    observed_at = _parse_timestamp(row.get("timestamp"))
                    if observed_at is None:
                        logger.warning(f"Row {idx} in {csv_path.name} has an unparseable timestamp, skipping")
                        stats["failed"] += 1
                        continue

                    severity = (row.get("severity") or "").strip().upper() or None
                    if severity and severity not in valid_severities:
                        logger.warning(f"Row {idx} in {csv_path.name} has unknown severity {severity!r}, skipping")
                        stats["failed"] += 1
                        continue

                    lat = _parse_float(row.get("latitude"))
                    lon = _parse_float(row.get("longitude"))

                    batch.append(
                        dict(
                            id=row_id,
                            source=row.get("source", "UNKNOWN"),
                            observed_at=observed_at,
                            detected_at=_parse_timestamp(row.get("generated_at")),
                            variable=row.get("variable", "UNKNOWN"),
                            observed_value=_parse_float(row.get("observed_value")),
                            baseline_value=_parse_float(row.get("baseline_value")),
                            deviation=_parse_float(row.get("deviation")),
                            method=row.get("method") or None,
                            threshold=_parse_float(row.get("threshold")),
                            anomaly_score=_parse_float(row.get("anomaly_score")),
                            severity=severity,
                            classification=row.get("classification") or None,
                            status=row.get("status") or None,
                            explanation=row.get("explanation") or None,
                            latitude=lat,
                            longitude=lon,
                            location_name=None,  # not present in source data, see note above
                            location=_point_wkt(lat, lon),
                        )
                    )

                    if len(batch) >= batch_size:
                        flush()

                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append({"index": idx, "error": str(e)})
                    logger.error(f"Row {idx} in {csv_path.name} failed: {e}")

            flush()  # final partial batch

        logger.info(
            f"{csv_path.name}: read={stats['read']} inserted={stats['inserted']} "
            f"skipped_existing={stats['skipped_existing']} failed={stats['failed']}"
        )
        return stats
    except Exception as e:
        session.rollback()
        logger.error(f"Ingestion of {csv_path} failed: {e}", exc_info=True)
        stats["failed"] += 1
        stats["errors"].append({"index": None, "error": str(e)})
        return stats
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--era5-path", default=str(DEFAULT_ERA5_PATH))
    parser.add_argument("--openmeteo-path", default=str(DEFAULT_OPENMETEO_PATH))
    parser.add_argument("--anomalies-path", default=str(DEFAULT_ANOMALIES_PATH))
    parser.add_argument("--database-url", default=None, help="Defaults to DATABASE_URL / Settings.DATABASE_URL")
    parser.add_argument("--observations-only", action="store_true")
    parser.add_argument("--anomalies-only", action="store_true")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows per bulk INSERT ... ON CONFLICT DO NOTHING statement (default {DEFAULT_BATCH_SIZE})",
    )
    args = parser.parse_args()

    database_url = args.database_url or get_settings().DATABASE_URL

    total_failed = 0

    if not args.anomalies_only:
        for path_str in (args.era5_path, args.openmeteo_path):
            path = Path(path_str)
            if not path.exists():
                logger.error(f"Observations file not found: {path}")
                total_failed += 1
                continue
            stats = ingest_observations(path, database_url, batch_size=args.batch_size)
            total_failed += stats["failed"]

    if not args.observations_only:
        anomalies_path = Path(args.anomalies_path)
        if not anomalies_path.exists():
            logger.error(f"Anomalies file not found: {anomalies_path}")
            total_failed += 1
        else:
            stats = ingest_anomalies(anomalies_path, database_url, batch_size=args.batch_size)
            total_failed += stats["failed"]

    if total_failed > 0:
        logger.warning(f"Ingestion completed with {total_failed} row-level failures - see warnings above")
        return 1

    logger.info("Ingestion completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
