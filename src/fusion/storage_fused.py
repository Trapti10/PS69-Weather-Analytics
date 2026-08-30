"""
Storage for Phase 2B fusion outputs. Writes to data/phase2/fused/ -- a
separate directory from Phase 2A's data/phase2/processed/, so nothing from
Phase 2A is overwritten (per Part 8's explicit instruction).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List, Dict, Any

FUSED_DIR = Path(__file__).resolve().parents[2] / "data" / "phase2" / "fused"


def save_era5_records(records, filename: str = "era5_weather_records.json"):
    FUSED_DIR.mkdir(parents=True, exist_ok=True)
    path = FUSED_DIR / filename
    with open(path, "w") as f:
        json.dump([r.to_dict() for r in records], f, indent=2, default=str)
    return path


def save_era5_records_csv(records, filename: str = "era5_weather_records.csv"):
    FUSED_DIR.mkdir(parents=True, exist_ok=True)
    path = FUSED_DIR / filename
    fieldnames = ["id", "source", "timestamp", "latitude", "longitude", "temperature",
                  "pressure", "rainfall", "wind_speed", "wind_direction",
                  "verification_status", "confidence_score", "quality_flags"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = r.to_dict()
            row["quality_flags"] = ";".join(row["quality_flags"])
            writer.writerow({k: row[k] for k in fieldnames})
    return path


def save_comparison_csv(fusion_results: List[Dict[str, Any]], filename: str = "source_comparison.csv"):
    """Flatten fusion results into one row per (record_pair, variable) for easy inspection in a spreadsheet."""
    FUSED_DIR.mkdir(parents=True, exist_ok=True)
    path = FUSED_DIR / filename
    fieldnames = ["pair_index", "match_status", "time_difference_minutes", "distance_km",
                  "variable", "era5_value", "imd_value", "absolute_difference",
                  "percent_difference", "agreement_flag"]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, result in enumerate(fusion_results):
            comparison = result.get("comparison", {})
            if not comparison:
                writer.writerow({
                    "pair_index": i, "match_status": result["match_status"],
                    "time_difference_minutes": result["temporal_alignment"]["time_difference_minutes"],
                    "distance_km": result["spatial_alignment"]["distance_km"],
                    "variable": None, "era5_value": None, "imd_value": None,
                    "absolute_difference": None, "percent_difference": None, "agreement_flag": None,
                })
                continue
            for var, c in comparison.items():
                values = list(c.items())
                writer.writerow({
                    "pair_index": i, "match_status": result["match_status"],
                    "time_difference_minutes": result["temporal_alignment"]["time_difference_minutes"],
                    "distance_km": result["spatial_alignment"]["distance_km"],
                    "variable": var,
                    "era5_value": values[0][1], "imd_value": values[1][1],
                    "absolute_difference": c["absolute_difference"],
                    "percent_difference": c["percent_difference"],
                    "agreement_flag": c["agreement_flag"],
                })
    return path


def save_fused_records(fusion_results: List[Dict[str, Any]], filename: str = "fused_weather_records.json"):
    FUSED_DIR.mkdir(parents=True, exist_ok=True)
    path = FUSED_DIR / filename
    with open(path, "w") as f:
        json.dump(fusion_results, f, indent=2, default=str)
    return path


def save_fused_records_csv(fusion_results: List[Dict[str, Any]], filename: str = "fused_weather_records.csv"):
    FUSED_DIR.mkdir(parents=True, exist_ok=True)
    path = FUSED_DIR / filename
    fieldnames = ["pair_index", "match_status", "confidence_score", "marginal_match",
                  "fused_temperature", "fused_pressure", "fused_rainfall", "fused_wind_speed"]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, result in enumerate(fusion_results):
            fusion = result.get("fusion", {})
            writer.writerow({
                "pair_index": i,
                "match_status": result["match_status"],
                "confidence_score": fusion.get("confidence_score"),
                "marginal_match": fusion.get("marginal_match"),
                "fused_temperature": fusion.get("temperature"),
                "fused_pressure": fusion.get("pressure"),
                "fused_rainfall": fusion.get("rainfall"),
                "fused_wind_speed": fusion.get("wind_speed"),
            })
    return path
