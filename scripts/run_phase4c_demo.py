"""
Phase 4C -- real-data demo.

Loads the project's real ERA5 and Open-Meteo hourly data (2024-2025,
Jabalpur), converts it to normalized WeatherRecords via the existing,
unmodified Phase 2B/2C adapters, runs Phase 4C anomaly detection on it,
saves the outputs to data/phase4c/, and prints the actual summary
statistics computed from the real run (never manufactured).

Also demonstrates the additive Phase 4A/4B integration points:
  - attaches matched anomalies onto the small existing Phase 4A demo
    output (data/phase4/weather_intelligence.json), saved to a NEW file
    (data/phase4c/weather_intelligence_with_anomalies.json) -- the
    original Phase 4A output file is never modified.
  - attaches observed-anomaly *context* onto the existing Phase 4B
    forecast records (data/phase4b/weather_intelligence_with_forecast.json),
    saved to a NEW file, without altering any forecasted value.

Run: python scripts/run_phase4c_demo.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from adapters.era5_adapter import era5_csv_to_records
from adapters.openmeteo_adapter import openmeteo_json_to_records

from phase4c.anomaly_detection import (
    run_anomaly_detection, AnomalyConfig, attach_anomaly_context_to_forecast,
)
from phase4c.anomaly_storage import (
    save_anomalies_json, save_anomalies_csv, save_summary_json, PHASE4C_DIR,
)

from phase4.weather_intelligence import WeatherIntelligence
from phase4c.anomaly_detection import attach_anomalies_to_intelligence


ERA5_RAW = ROOT / "data" / "raw" / "jabalpur_weather_2024_2025.csv"
OPENMETEO_RAW = ROOT / "data" / "raw" / "jabalpur_openmeteo_2024_2025.json"
PHASE4_INTEL_JSON = ROOT / "data" / "phase4" / "weather_intelligence.json"
PHASE4B_FORECAST_JSON = ROOT / "data" / "phase4b" / "weather_intelligence_with_forecast.json"


def build_summary(anomaly_records, prep_summary_by_source) -> dict:
    total = len(anomaly_records)
    anomalies_only = [a for a in anomaly_records if a.classification == "STATISTICAL_ANOMALY"]

    def _year(ts):
        return ts[:4] if ts else None

    def _month(ts):
        return ts[:7] if ts else None

    def _season(ts):
        if not ts:
            return None
        month = int(ts[5:7])
        # Indian meteorological seasons (documented convention, not a computed statistic):
        # winter: Dec-Feb, pre-monsoon/summer: Mar-May, monsoon: Jun-Sep, post-monsoon: Oct-Nov
        if month in (12, 1, 2):
            return "winter"
        if month in (3, 4, 5):
            return "pre_monsoon"
        if month in (6, 7, 8, 9):
            return "monsoon"
        return "post_monsoon"

    summary = {
        "total_observations_analyzed": total,
        "total_anomalies": len(anomalies_only),
        "anomaly_rate": round(len(anomalies_only) / total, 6) if total else None,
        "anomalies_by_source": dict(Counter(a.source for a in anomalies_only)),
        "anomalies_by_variable": dict(Counter(a.variable for a in anomalies_only)),
        "anomalies_by_severity": dict(Counter(a.severity for a in anomalies_only)),
        "anomalies_by_year": dict(Counter(_year(a.timestamp) for a in anomalies_only)),
        "anomalies_by_month": dict(sorted(Counter(_month(a.timestamp) for a in anomalies_only).items())),
        "anomalies_by_season": dict(Counter(_season(a.timestamp) for a in anomalies_only)),
        "status_counts": dict(Counter(a.status for a in anomaly_records)),
        "insufficient_history_count": sum(1 for a in anomaly_records if a.status == "INSUFFICIENT_HISTORY"),
        "missing_value_count": sum(1 for a in anomaly_records if a.status == "MISSING_VALUE"),
        "invalid_value_count": sum(1 for a in anomaly_records if a.status == "INVALID_VALUE"),
        "zero_variance_count": sum(1 for a in anomaly_records if a.status == "ZERO_VARIANCE"),
        "prep_summary_by_source": prep_summary_by_source,
        "config": AnomalyConfig().__dict__,
    }
    return summary


def main():
    print("Loading real ERA5 and Open-Meteo data via existing Phase 2B/2C adapters...")
    era5_records = era5_csv_to_records(str(ERA5_RAW))
    openmeteo_records = openmeteo_json_to_records(str(OPENMETEO_RAW))
    print(f"  ERA5: {len(era5_records)} records, Open-Meteo: {len(openmeteo_records)} records")

    all_records = era5_records + openmeteo_records
    config = AnomalyConfig()

    print("Running Phase 4C anomaly detection (rolling z-score / rolling percentile)...")
    anomaly_records, prep_summary_by_source = run_anomaly_detection(all_records, config)

    print(f"  {len(anomaly_records)} total variable-observations scored across both sources.")

    summary = build_summary(anomaly_records, prep_summary_by_source)
    anomalies_only = [a for a in anomaly_records if a.classification == "STATISTICAL_ANOMALY"]

    # NOTE ON WHAT GETS PERSISTED: `anomaly_records` (in memory, used for the
    # summary above) includes every scored variable-observation -- NORMAL,
    # INSUFFICIENT_HISTORY, MISSING_VALUE, etc. -- because the summary's
    # "total observations analyzed" and status counts need that full
    # picture. But data/phase4c/anomalies.{json,csv} store only the actual
    # STATISTICAL_ANOMALY findings (anomalies_only): persisting all ~140k
    # per-hour "NORMAL" evaluations to disk would be a multi-hundred-MB
    # file of near-zero information content. The aggregate counts for
    # everything else already live in anomaly_summary.json.
    print("Saving outputs to data/phase4c/ ...")
    json_path = save_anomalies_json(anomalies_only)
    csv_path = save_anomalies_csv(anomalies_only)
    summary_path = save_summary_json(summary)
    print(f"  {json_path}\n  {csv_path}\n  {summary_path}")
    print("\n--- Real-data summary ---")
    print(f"Total observations analyzed: {summary['total_observations_analyzed']}")
    print(f"Total anomalies: {summary['total_anomalies']} (rate: {summary['anomaly_rate']})")
    print(f"By variable: {summary['anomalies_by_variable']}")
    print(f"By severity: {summary['anomalies_by_severity']}")
    print(f"By source: {summary['anomalies_by_source']}")
    print(f"Status counts: {summary['status_counts']}")

    # --- Additive Phase 4A integration (does not modify data/phase4/) ---
    if PHASE4_INTEL_JSON.exists():
        print("\nAttaching matched anomalies onto existing Phase 4A intelligence demo output "
              "(additive -- new file only)...")
        with open(PHASE4_INTEL_JSON) as f:
            intel_raw = json.load(f)
        intel_records = [WeatherIntelligence.from_dict(d) for d in intel_raw]
        updated = [attach_anomalies_to_intelligence(intel, anomalies_only) for intel in intel_records]
        matched_count = sum(1 for u in updated if u.anomaly is not None)
        out_path = PHASE4C_DIR / "weather_intelligence_with_anomalies.json"
        with open(out_path, "w") as f:
            json.dump([u.to_dict() for u in updated], f, indent=2, default=str)
        print(f"  {matched_count}/{len(updated)} Phase 4A intelligence records had a matching "
              f"anomaly nearby -> {out_path}")
    else:
        print(f"\n(Skipping Phase 4A integration step -- {PHASE4_INTEL_JSON} not found.)")

    # --- Additive Phase 4B integration (does not modify data/phase4b/, never
    #     edits a forecasted value, never labels a forecast as an observation) ---
    if PHASE4B_FORECAST_JSON.exists():
        print("Attaching observed-anomaly context onto existing Phase 4B forecast records "
              "(additive -- new file only)...")
        with open(PHASE4B_FORECAST_JSON) as f:
            forecast_raw = json.load(f)
        updated_forecasts = [
            attach_anomaly_context_to_forecast(fr, anomalies_only) for fr in forecast_raw
        ]
        with_context = sum(1 for fr in updated_forecasts if fr.get("observed_anomaly_context"))
        out_path = PHASE4C_DIR / "forecast_with_anomaly_context.json"
        with open(out_path, "w") as f:
            json.dump(updated_forecasts, f, indent=2, default=str)
        print(f"  {with_context}/{len(updated_forecasts)} forecast records had observed-anomaly "
              f"context nearby -> {out_path}")
    else:
        print(f"(Skipping Phase 4B integration step -- {PHASE4B_FORECAST_JSON} not found.)")

    print("\nPhase 4C demo complete.")


if __name__ == "__main__":
    main()
