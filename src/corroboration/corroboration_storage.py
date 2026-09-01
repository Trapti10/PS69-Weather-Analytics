"""
Storage for Phase 3C corroboration/verification outputs. Writes to
data/phase3c/ -- a new, separate directory, so nothing from Phase 2, 2C,
3A, or 3B is overwritten (same convention as storage_fused_2c.py and
intelligence_storage.py before it).
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import List, Dict, Any

PHASE3C_DIR = Path(__file__).resolve().parents[2] / "data" / "phase3c"

CSV_FIELDS = [
    "report_id", "event_category", "predicted_event_category",
    "event_classification_confidence", "risk_label", "risk_score",
    "report_timestamp", "latitude", "longitude",
    "verification_status", "evidence_sources", "evidence_support_score",
    "verification_reasons",
]


def save_verification_results_json(results: List[Dict[str, Any]],
                                    filename: str = "corroborated_reports.json") -> Path:
    PHASE3C_DIR.mkdir(parents=True, exist_ok=True)
    path = PHASE3C_DIR / filename
    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    return path


def save_verification_results_csv(results: List[Dict[str, Any]],
                                   filename: str = "corroborated_reports.csv") -> Path:
    PHASE3C_DIR.mkdir(parents=True, exist_ok=True)
    path = PHASE3C_DIR / filename
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in results:
            row = dict(r)
            row["evidence_sources"] = "; ".join(row.get("evidence_sources", []))
            row["verification_reasons"] = " | ".join(row.get("verification_reasons", []))
            writer.writerow({k: row.get(k) for k in CSV_FIELDS})
    return path


def save_verification_summary(results: List[Dict[str, Any]],
                               filename: str = "verification_summary.json") -> Path:
    PHASE3C_DIR.mkdir(parents=True, exist_ok=True)
    path = PHASE3C_DIR / filename

    status_counts = Counter(r["verification_status"] for r in results)
    scores = [r["evidence_support_score"] for r in results if r["evidence_support_score"] is not None]
    avg_score = round(sum(scores) / len(scores), 4) if scores else None

    source_usage = Counter()
    for r in results:
        for s in r.get("evidence_sources", []):
            source_usage[s] += 1

    summary = {
        "total_reports": len(results),
        "verification_status_counts": dict(status_counts),
        "average_evidence_support_score": avg_score,
        "reports_with_a_score": len(scores),
        "evidence_source_usage_counts": dict(source_usage),
        "honest_note": (
            "evidence_support_score is a transparent mean of documented "
            "per-variable threshold verdicts, NOT a probability of truth. "
            "SUPPORTED means 'consistent with available weather evidence', "
            "never 'confirmed true'. ERA5 and Open-Meteo are model/reanalysis "
            "products, not ground truth. IMD evidence in this project is "
            "fixture-based (dated ~2026) and will not overlap the report's "
            "real 2024-2025 evidence window -- see IMD_TEMPORAL_UNAVAILABLE "
            "reasons in individual results."
        ),
    }
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return path
