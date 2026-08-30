"""
Storage layer for standardized WeatherRecords: JSON and CSV, appended
per ingestion run. Kept deliberately simple (flat files) for Phase 2 —
no database yet, since ingestion volume at this phase (a handful of
stations) does not justify one. See README/scaling notes for when this
should become a real datastore.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_record import WeatherRecord

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "phase2" / "processed"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "phase2" / "raw"

CSV_FIELDS = [
    "id", "source", "station_id", "timestamp", "ingested_at",
    "country", "state", "district", "city", "latitude", "longitude",
    "temperature", "humidity", "pressure", "rainfall", "wind_speed", "wind_direction",
    "event_type", "description", "verification_status", "confidence_score", "quality_flags",
]


def save_raw(raw_records: list, source_label: str) -> Path:
    """Save the untouched raw API/fixture response for audit purposes."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RAW_DIR / f"{source_label}_{ts}.json"
    with open(path, "w") as f:
        json.dump(raw_records, f, indent=2)
    return path


def save_records_json(records: List[WeatherRecord], filename: str = "weather_records.json") -> Path:
    """Append-or-create a JSON array file of standardized WeatherRecords."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / filename

    existing = []
    if path.exists():
        with open(path, "r") as f:
            existing = json.load(f)

    existing.extend([r.to_dict() for r in records])

    with open(path, "w") as f:
        json.dump(existing, f, indent=2, default=str)

    return path


def save_records_csv(records: List[WeatherRecord], filename: str = "weather_records.csv") -> Path:
    """Append-or-create a CSV file of standardized WeatherRecords."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / filename
    file_exists = path.exists()

    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        for r in records:
            row = r.to_dict()
            row["quality_flags"] = ";".join(row["quality_flags"])
            row.pop("raw_payload", None)  # keep CSV flat/readable; JSON retains full payload
            writer.writerow(row)

    return path
