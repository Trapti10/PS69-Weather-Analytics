"""
Storage for Phase 4A unified Weather Intelligence outputs. Writes to
data/phase4/ -- a new, separate directory, so nothing from Phase 2, 2C, 3A,
3B, or 3C is overwritten (same convention as intelligence_storage.py and
corroboration_storage.py before it).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import List

sys.path.append(str(Path(__file__).resolve().parents[1]))
from phase4.weather_intelligence import WeatherIntelligence

PHASE4_DIR = Path(__file__).resolve().parents[2] / "data" / "phase4"

CSV_FIELDS = [
    "id", "generated_at", "timestamp", "latitude", "longitude",
    "country", "state", "district", "city",
    "temperature", "humidity", "pressure", "rainfall", "wind_speed", "wind_direction",
    "contributing_sources",
    "source_agreement_confidence", "source_agreement_match_status", "source_agreement_marginal",
    "corroboration_status", "evidence_support_score", "overall_confidence", "confidence_method",
    "matched_report_ids",
]


def save_weather_intelligence_json(records: List[WeatherIntelligence],
                                    filename: str = "weather_intelligence.json") -> Path:
    PHASE4_DIR.mkdir(parents=True, exist_ok=True)
    path = PHASE4_DIR / filename
    with open(path, "w") as f:
        json.dump([r.to_dict() for r in records], f, indent=2, default=str)
    return path


def save_weather_intelligence_csv(records: List[WeatherIntelligence],
                                   filename: str = "weather_intelligence.csv") -> Path:
    PHASE4_DIR.mkdir(parents=True, exist_ok=True)
    path = PHASE4_DIR / filename
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in records:
            d = r.to_dict()
            wv = d.get("weather_variables", {}) or {}
            row = {
                "id": d["id"], "generated_at": d["generated_at"], "timestamp": d["timestamp"],
                "latitude": d["latitude"], "longitude": d["longitude"],
                "country": d["country"], "state": d["state"], "district": d["district"], "city": d["city"],
                "temperature": wv.get("temperature"), "humidity": wv.get("humidity"),
                "pressure": wv.get("pressure"), "rainfall": wv.get("rainfall"),
                "wind_speed": wv.get("wind_speed"), "wind_direction": wv.get("wind_direction"),
                "contributing_sources": "; ".join(d.get("contributing_sources", [])),
                "source_agreement_confidence": d["source_agreement_confidence"],
                "source_agreement_match_status": d["source_agreement_match_status"],
                "source_agreement_marginal": d["source_agreement_marginal"],
                "corroboration_status": d["corroboration_status"],
                "evidence_support_score": d["evidence_support_score"],
                "overall_confidence": d["overall_confidence"],
                "confidence_method": d["confidence_method"],
                "matched_report_ids": "; ".join(
                    str(rep.get("report_id")) for rep in d.get("report_evidence", [])
                ),
            }
            writer.writerow(row)
    return path


def load_weather_intelligence_json(filename: str = "weather_intelligence.json") -> List[WeatherIntelligence]:
    path = PHASE4_DIR / filename
    with open(path, "r") as f:
        raw = json.load(f)
    return [WeatherIntelligence.from_dict(item) for item in raw]
