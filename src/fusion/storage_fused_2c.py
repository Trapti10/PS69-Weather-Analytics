"""
Storage for Phase 2C (ERA5 + Open-Meteo cross-model comparison) outputs.
Writes to data/phase2c/fused/ -- a NEW directory, separate from Phase 2A's
data/phase2/processed/ and Phase 2B's data/phase2/fused/, so nothing from
either earlier phase is overwritten or touched.

Deliberately a separate module from src/fusion/storage_fused.py rather than
a modification of it: Phase 2B's CSV writers hardcode "era5_value"/
"imd_value" column names tied to that specific pairing, and per this
project's rule of not modifying completed phases, Phase 2C gets its own
(source-label-aware) writers instead of repurposing those column names for
a different pairing.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List, Dict, Any

FUSED_2C_DIR = Path(__file__).resolve().parents[2] / "data" / "phase2c" / "fused"


def save_openmeteo_records(records, filename: str = "openmeteo_weather_records.json"):
    FUSED_2C_DIR.mkdir(parents=True, exist_ok=True)
    path = FUSED_2C_DIR / filename
    with open(path, "w") as f:
        json.dump([r.to_dict() for r in records], f, indent=2, default=str)
    return path


def save_openmeteo_records_csv(records, filename: str = "openmeteo_weather_records.csv"):
    FUSED_2C_DIR.mkdir(parents=True, exist_ok=True)
    path = FUSED_2C_DIR / filename
    fieldnames = ["id", "source", "timestamp", "latitude", "longitude", "temperature",
                  "humidity", "pressure", "rainfall", "wind_speed", "wind_direction",
                  "verification_status", "confidence_score", "quality_flags"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = r.to_dict()
            row["quality_flags"] = ";".join(row["quality_flags"])
            writer.writerow({k: row[k] for k in fieldnames})
    return path


def save_comparison_csv_2c(fusion_results: List[Dict[str, Any]], label_a: str, label_b: str,
                            filename: str = "era5_openmeteo_comparison.csv"):
    """Flatten fusion results into one row per (record_pair, variable)."""
    FUSED_2C_DIR.mkdir(parents=True, exist_ok=True)
    path = FUSED_2C_DIR / filename
    key_a, key_b = f"{label_a.lower()}_value", f"{label_b.lower()}_value"
    fieldnames = ["pair_index", "timestamp", "match_status", "time_difference_minutes",
                  "distance_km", "variable", key_a, key_b, "absolute_difference",
                  "percent_difference", "agreement_flag"]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, result in enumerate(fusion_results):
            ts = result["temporal_alignment"].get("era5_timestamp")
            comparison = result.get("comparison", {})
            if not comparison:
                writer.writerow({
                    "pair_index": i, "timestamp": ts, "match_status": result["match_status"],
                    "time_difference_minutes": result["temporal_alignment"]["time_difference_minutes"],
                    "distance_km": result["spatial_alignment"]["distance_km"],
                    "variable": None, key_a: None, key_b: None,
                    "absolute_difference": None, "percent_difference": None, "agreement_flag": None,
                })
                continue
            for var, c in comparison.items():
                writer.writerow({
                    "pair_index": i, "timestamp": ts, "match_status": result["match_status"],
                    "time_difference_minutes": result["temporal_alignment"]["time_difference_minutes"],
                    "distance_km": result["spatial_alignment"]["distance_km"],
                    "variable": var,
                    key_a: c[key_a], key_b: c[key_b],
                    "absolute_difference": c["absolute_difference"],
                    "percent_difference": c["percent_difference"],
                    "agreement_flag": c["agreement_flag"],
                })
    return path


def save_fused_records_csv_2c(fusion_results: List[Dict[str, Any]],
                               filename: str = "era5_openmeteo_fused_records.csv"):
    FUSED_2C_DIR.mkdir(parents=True, exist_ok=True)
    path = FUSED_2C_DIR / filename
    fieldnames = ["pair_index", "timestamp", "match_status", "confidence_score", "marginal_match",
                  "fused_temperature", "fused_pressure", "fused_rainfall", "fused_wind_speed"]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, result in enumerate(fusion_results):
            fusion = result.get("fusion", {})
            ts = result["temporal_alignment"].get("era5_timestamp")
            writer.writerow({
                "pair_index": i,
                "timestamp": ts,
                "match_status": result["match_status"],
                "confidence_score": fusion.get("confidence_score"),
                "marginal_match": fusion.get("marginal_match"),
                "fused_temperature": fusion.get("temperature"),
                "fused_pressure": fusion.get("pressure"),
                "fused_rainfall": fusion.get("rainfall"),
                "fused_wind_speed": fusion.get("wind_speed"),
            })
    return path


def save_summary_json(summary: Dict[str, Any], filename: str = "phase2c_summary.json"):
    FUSED_2C_DIR.mkdir(parents=True, exist_ok=True)
    path = FUSED_2C_DIR / filename
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return path
