"""
Storage for Phase 4C anomaly-detection outputs. Writes to data/phase4c/ --
a new, separate directory, so nothing from Phase 1-4B is overwritten (same
convention as phase4/intelligence_storage.py and
corroboration/corroboration_storage.py before it).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

from phase4c.anomaly_detection import AnomalyRecord

PHASE4C_DIR = Path(__file__).resolve().parents[2] / "data" / "phase4c"

CSV_FIELDS = [
    "id", "generated_at", "timestamp", "latitude", "longitude", "location",
    "source", "variable", "observed_value", "baseline_value", "deviation",
    "method", "threshold", "anomaly_score", "severity", "classification",
    "status", "explanation",
]


def save_anomalies_json(records: List[AnomalyRecord], filename: str = "anomalies.json") -> Path:
    PHASE4C_DIR.mkdir(parents=True, exist_ok=True)
    path = PHASE4C_DIR / filename
    with open(path, "w") as f:
        json.dump([r.to_dict() for r in records], f, indent=2, default=str)
    return path


def save_anomalies_csv(records: List[AnomalyRecord], filename: str = "anomalies.csv") -> Path:
    PHASE4C_DIR.mkdir(parents=True, exist_ok=True)
    path = PHASE4C_DIR / filename
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in records:
            d = r.to_dict()
            writer.writerow({k: d.get(k) for k in CSV_FIELDS})
    return path


def load_anomalies_json(filename: str = "anomalies.json") -> List[AnomalyRecord]:
    path = PHASE4C_DIR / filename
    with open(path, "r") as f:
        raw = json.load(f)
    known_fields = set(AnomalyRecord.__dataclass_fields__)
    return [AnomalyRecord(**{k: v for k, v in item.items() if k in known_fields}) for item in raw]


def save_summary_json(summary: dict, filename: str = "anomaly_summary.json") -> Path:
    PHASE4C_DIR.mkdir(parents=True, exist_ok=True)
    path = PHASE4C_DIR / filename
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return path
