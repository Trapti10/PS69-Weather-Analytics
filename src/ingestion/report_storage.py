"""
Storage for Phase 3A normalized WeatherReport objects. Writes to
data/phase3/processed/ -- a new directory, separate from Phase 1/2A/2B/2C
outputs, so nothing from earlier phases is touched.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "phase3" / "processed"

CSV_FIELDS = [
    "report_id", "source_type", "source_name", "author_id_or_hash", "timestamp",
    "ingestion_timestamp", "city", "state", "latitude", "longitude", "text",
    "event_type", "raw_event_type", "verification_status", "source_reliability",
    "is_suspicious", "is_duplicate", "duplicate_hash", "duplicate_group_id",
    "quality_flags",
]


def save_reports_json(reports: List, filename: str) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / filename
    with open(path, "w") as f:
        json.dump([r.to_dict() for r in reports], f, indent=2, default=str)
    return path


def save_reports_csv(reports: List, filename: str) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / filename
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in reports:
            row = r.to_dict()
            row["quality_flags"] = ";".join(row["quality_flags"])
            writer.writerow({k: row[k] for k in CSV_FIELDS})
    return path
