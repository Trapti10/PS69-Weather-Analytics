"""Idempotently load the project's real weather-intelligence datasets into PostgreSQL."""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.api.config import get_settings  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


DEFAULT_ERA5_PATH = (
    REPO_ROOT
    / "data"
    / "phase2"
    / "fused"
    / "era5_weather_records.csv"
)

DEFAULT_OPENMETEO_PATH = (
    REPO_ROOT
    / "data"
    / "phase2c"
    / "fused"
    / "openmeteo_weather_records.csv"
)

DEFAULT_ANOMALIES_PATH = (
    REPO_ROOT
    / "data"
    / "phase4c"
    / "anomalies.csv"
)


def _parse_float(value: str | None) -> Optional[float]:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: str | None) -> Optional[datetime]:
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None


def _point_wkt(
    lat: Optional[float],
    lon: Optional[float],
) -> Optional[str]:
    if (
        lat is None
        or lon is None
        or not (-90 <= lat <= 90)
        or not (-180 <= lon <= 180)
    ):
        return None

    return f"POINT({lon} {lat})"


def _insert_observation_batch(conn, statement, batch: list[dict]) -> tuple[int, int]:
    """
    Insert one batch using a single PostgreSQL statement.

    Returns:
        (inserted_count, skipped_count)
    """

    if not batch:
        return 0, 0

    # Build a single INSERT statement containing all rows in this batch.
    values_sql = []

    parameters = {}

    for index, item in enumerate(batch):
        prefix = f"p{index}"

        values_sql.append(
            f"""
            (
                :{prefix}_id,
                :{prefix}_source,
                :{prefix}_observed_at,
                :{prefix}_latitude,
                :{prefix}_longitude,
                NULL,
                :{prefix}_temperature,
                :{prefix}_humidity,
                :{prefix}_rainfall,
                :{prefix}_wind_speed,
                :{prefix}_wind_direction,
                :{prefix}_pressure,
                :{prefix}_verification_status,
                :{prefix}_confidence_score,
                :{prefix}_quality_flags,
                ST_GeomFromText(:{prefix}_location, 4326)
            )
            """
        )

        parameters.update(
            {
                f"{prefix}_id": item["id"],
                f"{prefix}_source": item["source"],
                f"{prefix}_observed_at": item["observed_at"],
                f"{prefix}_latitude": item["latitude"],
                f"{prefix}_longitude": item["longitude"],
                f"{prefix}_temperature": item["temperature"],
                f"{prefix}_humidity": item["humidity"],
                f"{prefix}_rainfall": item["rainfall"],
                f"{prefix}_wind_speed": item["wind_speed"],
                f"{prefix}_wind_direction": item["wind_direction"],
                f"{prefix}_pressure": item["pressure"],
                f"{prefix}_verification_status": item[
                    "verification_status"
                ],
                f"{prefix}_confidence_score": item[
                    "confidence_score"
                ],
                f"{prefix}_quality_flags": item["quality_flags"],
                f"{prefix}_location": item["location"],
            }
        )

    batch_statement = text(
        f"""
        INSERT INTO weather_observations
        (
            id,
            source,
            observed_at,
            latitude,
            longitude,
            location_name,
            temperature,
            humidity,
            rainfall,
            wind_speed,
            wind_direction,
            pressure,
            verification_status,
            confidence_score,
            quality_flags,
            location
        )
        VALUES
        {",".join(values_sql)}
        ON CONFLICT (id) DO NOTHING
        RETURNING id
        """
    )

    result = conn.execute(
        batch_statement,
        parameters,
    )

    inserted = len(result.fetchall())
    skipped = len(batch) - inserted

    return inserted, skipped


def ingest_observations(
    csv_path: Path,
    database_url: str,
    batch_size: int = 2000,
) -> dict:

    stats = {
        "read": 0,
        "inserted": 0,
        "skipped_existing": 0,
        "failed": 0,
    }

    engine = create_engine(
        database_url,
        echo=False,
    )

    with engine.begin() as conn:
        with csv_path.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as handle:

            reader = csv.DictReader(handle)

            required = {
                "id",
                "source",
                "timestamp",
                "latitude",
                "longitude",
            }

            missing = required - set(
                reader.fieldnames or []
            )

            if missing:
                raise ValueError(
                    f"{csv_path} is missing required columns: {missing}"
                )

            batch: list[dict] = []

            for row in reader:
                stats["read"] += 1

                observed_at = _parse_timestamp(
                    row.get("timestamp")
                )

                row_id = row.get("id")

                if not row_id or observed_at is None:
                    stats["failed"] += 1
                    continue

                lat = _parse_float(
                    row.get("latitude")
                )

                lon = _parse_float(
                    row.get("longitude")
                )

                batch.append(
                    {
                        "id": row_id,
                        "source": (
                            row.get("source")
                            or "UNKNOWN"
                        ),
                        "observed_at": observed_at,
                        "latitude": lat,
                        "longitude": lon,
                        "temperature": _parse_float(
                            row.get("temperature")
                        ),
                        "humidity": _parse_float(
                            row.get("humidity")
                        ),
                        "rainfall": _parse_float(
                            row.get("rainfall")
                        ),
                        "wind_speed": _parse_float(
                            row.get("wind_speed")
                        ),
                        "wind_direction": _parse_float(
                            row.get("wind_direction")
                        ),
                        "pressure": _parse_float(
                            row.get("pressure")
                        ),
                        "verification_status": (
                            row.get(
                                "verification_status"
                            )
                            or None
                        ),
                        "confidence_score": _parse_float(
                            row.get("confidence_score")
                        ),
                        "quality_flags": (
                            row.get("quality_flags")
                            or None
                        ),
                        "location": _point_wkt(
                            lat,
                            lon,
                        ),
                    }
                )

                if len(batch) >= batch_size:
                    inserted, skipped = (
                        _insert_observation_batch(
                            conn,
                            None,
                            batch,
                        )
                    )

                    stats["inserted"] += inserted
                    stats["skipped_existing"] += skipped

                    batch = []

                    logger.info(
                        "%s: processed %s rows | inserted=%s skipped=%s failed=%s",
                        csv_path.name,
                        stats["read"],
                        stats["inserted"],
                        stats["skipped_existing"],
                        stats["failed"],
                    )

            # Process final partial batch
            if batch:
                inserted, skipped = (
                    _insert_observation_batch(
                        conn,
                        None,
                        batch,
                    )
                )

                stats["inserted"] += inserted
                stats["skipped_existing"] += skipped

    engine.dispose()

    logger.info(
        "%s: %s",
        csv_path.name,
        stats,
    )

    return stats


def _insert_anomaly_batch(
    conn,
    batch: list[dict],
) -> tuple[int, int]:
    """
    Insert one anomaly batch using a single PostgreSQL statement.

    Returns:
        (inserted_count, skipped_count)
    """

    if not batch:
        return 0, 0

    values_sql = []
    parameters = {}

    for index, item in enumerate(batch):
        prefix = f"p{index}"

        values_sql.append(
            f"""
            (
                :{prefix}_id,
                :{prefix}_source,
                :{prefix}_observed_at,
                :{prefix}_detected_at,
                :{prefix}_variable,
                :{prefix}_observed_value,
                :{prefix}_baseline_value,
                :{prefix}_deviation,
                :{prefix}_method,
                :{prefix}_threshold,
                :{prefix}_anomaly_score,
                :{prefix}_severity,
                :{prefix}_classification,
                :{prefix}_status,
                :{prefix}_explanation,
                :{prefix}_latitude,
                :{prefix}_longitude,
                NULL,
                ST_GeomFromText(:{prefix}_location, 4326)
            )
            """
        )

        parameters.update(
            {
                f"{prefix}_id": item["id"],
                f"{prefix}_source": item["source"],
                f"{prefix}_observed_at": item["observed_at"],
                f"{prefix}_detected_at": item["detected_at"],
                f"{prefix}_variable": item["variable"],
                f"{prefix}_observed_value": item[
                    "observed_value"
                ],
                f"{prefix}_baseline_value": item[
                    "baseline_value"
                ],
                f"{prefix}_deviation": item["deviation"],
                f"{prefix}_method": item["method"],
                f"{prefix}_threshold": item["threshold"],
                f"{prefix}_anomaly_score": item[
                    "anomaly_score"
                ],
                f"{prefix}_severity": item["severity"],
                f"{prefix}_classification": item[
                    "classification"
                ],
                f"{prefix}_status": item["status"],
                f"{prefix}_explanation": item[
                    "explanation"
                ],
                f"{prefix}_latitude": item["latitude"],
                f"{prefix}_longitude": item["longitude"],
                f"{prefix}_location": item["location"],
            }
        )

    batch_statement = text(
        f"""
        INSERT INTO weather_anomalies
        (
            id,
            source,
            observed_at,
            detected_at,
            variable,
            observed_value,
            baseline_value,
            deviation,
            method,
            threshold,
            anomaly_score,
            severity,
            classification,
            status,
            explanation,
            latitude,
            longitude,
            location_name,
            location
        )
        VALUES
        {",".join(values_sql)}
        ON CONFLICT (id) DO NOTHING
        RETURNING id
        """
    )

    result = conn.execute(
        batch_statement,
        parameters,
    )

    inserted = len(result.fetchall())
    skipped = len(batch) - inserted

    return inserted, skipped


def ingest_anomalies(
    csv_path: Path,
    database_url: str,
    batch_size: int = 2000,
) -> dict:

    stats = {
        "read": 0,
        "inserted": 0,
        "skipped_existing": 0,
        "failed": 0,
    }

    engine = create_engine(
        database_url,
        echo=False,
    )

    with engine.begin() as conn:
        with csv_path.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as handle:

            reader = csv.DictReader(handle)

            required = {
                "id",
                "source",
                "timestamp",
                "variable",
                "severity",
            }

            missing = required - set(
                reader.fieldnames or []
            )

            if missing:
                raise ValueError(
                    f"{csv_path} is missing required columns: {missing}"
                )

            valid_severities = {
                "LOW",
                "MEDIUM",
                "HIGH",
                "CRITICAL",
            }

            batch: list[dict] = []

            for row in reader:
                stats["read"] += 1

                row_id = row.get("id")

                observed_at = _parse_timestamp(
                    row.get("timestamp")
                )

                severity = (
                    row.get("severity") or ""
                ).strip().upper()

                if (
                    not row_id
                    or observed_at is None
                    or severity not in valid_severities
                ):
                    stats["failed"] += 1
                    continue

                lat = _parse_float(
                    row.get("latitude")
                )

                lon = _parse_float(
                    row.get("longitude")
                )

                batch.append(
                    {
                        "id": row_id,
                        "source": (
                            row.get("source")
                            or "UNKNOWN"
                        ),
                        "observed_at": observed_at,
                        "detected_at": _parse_timestamp(
                            row.get("generated_at")
                        ),
                        "variable": (
                            row.get("variable")
                            or "UNKNOWN"
                        ),
                        "observed_value": _parse_float(
                            row.get("observed_value")
                        ),
                        "baseline_value": _parse_float(
                            row.get("baseline_value")
                        ),
                        "deviation": _parse_float(
                            row.get("deviation")
                        ),
                        "method": (
                            row.get("method")
                            or None
                        ),
                        "threshold": _parse_float(
                            row.get("threshold")
                        ),
                        "anomaly_score": _parse_float(
                            row.get("anomaly_score")
                        ),
                        "severity": severity,
                        "classification": (
                            row.get("classification")
                            or None
                        ),
                        "status": (
                            row.get("status")
                            or None
                        ),
                        "explanation": (
                            row.get("explanation")
                            or None
                        ),
                        "latitude": lat,
                        "longitude": lon,
                        "location": _point_wkt(
                            lat,
                            lon,
                        ),
                    }
                )

                if len(batch) >= batch_size:
                    inserted, skipped = (
                        _insert_anomaly_batch(
                            conn,
                            batch,
                        )
                    )

                    stats["inserted"] += inserted
                    stats["skipped_existing"] += skipped

                    batch = []

                    logger.info(
                        "%s: processed %s rows | inserted=%s skipped=%s failed=%s",
                        csv_path.name,
                        stats["read"],
                        stats["inserted"],
                        stats["skipped_existing"],
                        stats["failed"],
                    )

            # Process final partial batch
            if batch:
                inserted, skipped = (
                    _insert_anomaly_batch(
                        conn,
                        batch,
                    )
                )

                stats["inserted"] += inserted
                stats["skipped_existing"] += skipped

    engine.dispose()

    logger.info(
        "%s: %s",
        csv_path.name,
        stats,
    )

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--era5-path",
        default=str(DEFAULT_ERA5_PATH),
    )

    parser.add_argument(
        "--openmeteo-path",
        default=str(DEFAULT_OPENMETEO_PATH),
    )

    parser.add_argument(
        "--anomalies-path",
        default=str(DEFAULT_ANOMALIES_PATH),
    )

    parser.add_argument(
        "--database-url",
        default=None,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=2000,
    )

    parser.add_argument(
        "--observations-only",
        action="store_true",
    )

    parser.add_argument(
        "--anomalies-only",
        action="store_true",
    )

    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error(
            "--batch-size must be at least 1"
        )

    database_url = (
        args.database_url
        or get_settings().DATABASE_URL
    )

    failures = 0

    if not args.anomalies_only:
        for path in (
            Path(args.era5_path),
            Path(args.openmeteo_path),
        ):
            if not path.exists():
                logger.error(
                    "Observations file not found: %s",
                    path,
                )

                failures += 1
                continue

            failures += ingest_observations(
                path,
                database_url,
                args.batch_size,
            )["failed"]

    if not args.observations_only:
        path = Path(args.anomalies_path)

        if not path.exists():
            logger.error(
                "Anomalies file not found: %s",
                path,
            )

            failures += 1

        else:
            failures += ingest_anomalies(
                path,
                database_url,
                args.batch_size,
            )["failed"]

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())