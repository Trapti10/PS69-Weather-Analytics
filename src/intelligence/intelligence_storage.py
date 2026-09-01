"""
Storage for Phase 3B intelligence outputs. Writes to data/phase3b/ -- a
separate directory from Phase 3A's data/phase3/processed/, so nothing from
Phase 3A is overwritten (same convention as Phase 2C's storage_fused_2c.py
relative to Phase 2B's storage_fused.py).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_report import WeatherReport

PHASE3B_DIR = Path(__file__).resolve().parents[2] / "data" / "phase3b"

CSV_FIELDS = [
    "report_id", "source_type", "source_name", "timestamp", "city", "state",
    "latitude", "longitude", "event_type", "verification_status", "source_reliability",
    "is_suspicious", "is_duplicate",
    "semantic_similarity_score", "semantic_duplicate_status", "matched_report_id", "similarity_method",
    "predicted_event_category", "event_classification_confidence", "classification_method",
    "risk_score", "risk_label", "risk_reasons",
    "intelligence_processed_at",
]


def save_intelligent_reports_json(reports: List[WeatherReport],
                                   filename: str = "intelligent_reports.json") -> Path:
    PHASE3B_DIR.mkdir(parents=True, exist_ok=True)
    path = PHASE3B_DIR / filename
    with open(path, "w") as f:
        json.dump([r.to_dict() for r in reports], f, indent=2, default=str)
    return path


def save_intelligent_reports_csv(reports: List[WeatherReport],
                                  filename: str = "intelligent_reports.csv") -> Path:
    PHASE3B_DIR.mkdir(parents=True, exist_ok=True)
    path = PHASE3B_DIR / filename
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in reports:
            row = r.to_dict()
            row["risk_reasons"] = "; ".join(row["risk_reasons"])
            writer.writerow({k: row[k] for k in CSV_FIELDS})
    return path
