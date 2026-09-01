#!/usr/bin/env python3
"""
Phase 4B demonstration: advanced multi-horizon ML trained and evaluated on
the REAL Phase 1 cleaned dataset (data/processed/jabalpur_clean.csv,
17,544 real hourly ERA5 rows for Jabalpur, 2024-01-01 to 2025-12-31).

WHAT THIS SCRIPT DOES:
  1. Loads the real cleaned dataset (same file Phase 1's own notebooks 04/05
     used -- not re-downloaded, not re-derived).
  2. Builds leakage-safe multi-horizon features (src/phase4b/feature_engineering.py).
  3. Splits chronologically (TRAIN -> VALIDATION -> TEST, never shuffled).
  4. Trains + evaluates RandomForest and HistGradientBoosting for
     temperature (5 horizons) and rainfall occurrence (5 horizons).
  5. Compares the 1-hour temperature result against Phase 1's own recorded
     baseline (reports/findings.md: Random Forest MAE 0.439, RMSE 0.621, R2 0.989).
  6. Saves all trained models + metadata under models/phase4b/.
  7. Writes data/phase4b/model_comparison.{csv,json} and forecast_results.json.
  8. Integrates one real Phase 4B forecast into a real Phase 4A
     WeatherIntelligence record (backward-compatible, additive only).

Does NOT modify data/processed/, data/phase4/, or any earlier phase's files.
"""
import sys
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from phase4b.feature_engineering import (
    build_temperature_feature_set, build_rainfall_feature_set,
    temperature_feature_columns, rainfall_feature_columns, HORIZONS,
)
from phase4b.time_series_ml import (
    three_way_chronological_split, train_temperature_models,
    train_rainfall_models, comparison_rows,
)
from phase4b.model_persistence import save_model, MODELS_ROOT
from phase4b.intelligence_integration import build_forecast_field, attach_phase4b_forecast
from phase4.weather_intelligence import WeatherIntelligence
from phase4.intelligence_storage import load_weather_intelligence_json

DATA_PHASE4B_DIR = PROJECT_ROOT / "data" / "phase4b"

# Phase 1's own recorded baseline (reports/findings.md, Track A, 1h-ahead,
# Random Forest, test set Sep-Dec 2025). Captured exactly, not re-derived.
PHASE1_BASELINE_1H = {"MAE": 0.439, "RMSE": 0.621, "R2": 0.989}


def print_section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def main():
    print_section("PHASE 4B DEMO -- Advanced multi-horizon ML (real data)")
    DATA_PHASE4B_DIR.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "jabalpur_clean.csv")
    print(f"Loaded {len(raw)} real cleaned ERA5 rows: "
          f"{raw['valid_time'].min()} -> {raw['valid_time'].max()}")

    forecast_results = {"temperature": {}, "rainfall": {}}
    saved_model_paths = list(MODELS_ROOT.rglob("*.pkl"))

    # NOTE ON EXECUTION: training all 10 target/horizon combinations
    # (2 targets x 5 horizons x {RandomForest, HistGradientBoosting}) on the
    # full 17,544-row real dataset on this machine's single CPU core takes
    # roughly 15-20 minutes in total -- longer than one interactive tool
    # call's time budget allows. scripts/_phase4b_worker.py contains the
    # IDENTICAL training/evaluation/saving logic below, factored out so each
    # target/horizon could be run as its own call; its results are appended
    # to data/phase4b/_partial_comparison.jsonl. If that file already
    # contains all 30 expected rows (2 targets x 5 horizons x 3 models
    # [Naive/RF/HistGB]), this script reuses them instead of re-training
    # from scratch (models are already saved under models/phase4b/ either
    # way). Otherwise it trains everything itself, in-process, exactly as
    # shown below.
    partial_path = DATA_PHASE4B_DIR / "_partial_comparison.jsonl"
    all_comparison_rows = []
    if partial_path.exists():
        with open(partial_path) as f:
            all_comparison_rows = [json.loads(line) for line in f if line.strip()]

    have_all_rows = len(all_comparison_rows) == len(HORIZONS) * 2 * 3

    if have_all_rows:
        print_section("Reusing already-trained/evaluated Phase 4B results")
        print(f"Loaded {len(all_comparison_rows)} comparison rows from {partial_path} "
              f"(produced by scripts/_phase4b_worker.py running this script's own "
              f"src/phase4b training functions on the real dataset above).")
        for h in HORIZONS:
            for target in ("temperature", "rainfall"):
                rows_h = [r for r in all_comparison_rows if r["Target"] == target and r["Horizon_h"] == h]
                metric_key = "MAE" if target == "temperature" else "F1"
                better = "min" if target == "temperature" else "max"
                candidates = [r for r in rows_h if r["Model"] in ("RandomForest", "HistGradientBoosting")]
                best = (min if better == "min" else max)(candidates, key=lambda r: r[metric_key] or 0)
                forecast_results[target][h] = {"best_model": best["Model"], **{
                    k: v for k, v in best.items() if k not in ("Model", "Target", "Horizon_h")
                }}
    else:
        # ---- Temperature: multi-horizon regression -----------------------------
        print_section("Temperature forecasting -- multi-horizon")
        for h in HORIZONS:
            feat = build_temperature_feature_set(raw, horizon=h)
            train, val, test = three_way_chronological_split(feat)
            cols = temperature_feature_columns(feat, horizon=h)
            target_col = f"target_t2m_h{h}"

            results = train_temperature_models(train, test, cols, target_col, horizon=h)
            all_comparison_rows.extend(comparison_rows("temperature", h, results))

            for model_name in ["RandomForest", "HistGradientBoosting"]:
                r = results[model_name]
                path = save_model(
                    r["model"], "temperature", model_name, h, cols, r["metrics"],
                    train_range=[str(train["valid_time"].min()), str(train["valid_time"].max())],
                )
                saved_model_paths.append(path)

            best_name = min(
                ["RandomForest", "HistGradientBoosting"],
                key=lambda n: results[n]["metrics"]["MAE"],
            )
            m = results[best_name]["metrics"]
            forecast_results["temperature"][h] = {"best_model": best_name, **m}
            print(f"  h={h:>2}h  NaivePersistence MAE={results['NaivePersistence']['metrics']['MAE']:.4f}  "
                  f"RandomForest MAE={results['RandomForest']['metrics']['MAE']:.4f}  "
                  f"HistGB MAE={results['HistGradientBoosting']['metrics']['MAE']:.4f}  "
                  f"(train={len(train)}, test={len(test)})")

    print_section("Baseline comparison -- 1h temperature forecast")
    rf_1h = next(r for r in all_comparison_rows if r["Target"] == "temperature"
                 and r["Horizon_h"] == 1 and r["Model"] == "RandomForest")
    hgb_1h = next(r for r in all_comparison_rows if r["Target"] == "temperature"
                  and r["Horizon_h"] == 1 and r["Model"] == "HistGradientBoosting")
    print(f"Phase 1 baseline (RandomForest, 1h, reports/findings.md): {PHASE1_BASELINE_1H}")
    print(f"Phase 4B RandomForest (1h, this run):        MAE={rf_1h['MAE']:.4f} RMSE={rf_1h['RMSE']:.4f} R2={rf_1h['R2']:.4f}")
    print(f"Phase 4B HistGradientBoosting (1h, this run): MAE={hgb_1h['MAE']:.4f} RMSE={hgb_1h['RMSE']:.4f} R2={hgb_1h['R2']:.4f}")
    for name, row in [("RandomForest", rf_1h), ("HistGradientBoosting", hgb_1h)]:
        delta = PHASE1_BASELINE_1H["MAE"] - row["MAE"]
        verdict = "IMPROVED" if delta > 0 else ("WORSE" if delta < 0 else "UNCHANGED")
        print(f"  {name} vs Phase 1 baseline MAE: delta={delta:+.4f} -> {verdict} "
              f"(honest comparison; feature set differs from Phase 1's, see README)")

    if not have_all_rows:
        # ---- Rainfall: multi-horizon classification -----------------------------
        print_section("Rainfall occurrence -- multi-horizon")
        for h in HORIZONS:
            feat = build_rainfall_feature_set(raw, horizon=h)
            train, val, test = three_way_chronological_split(feat)
            cols = rainfall_feature_columns(feat, horizon=h)
            target_col = f"target_rain_next{h}h"

            results = train_rainfall_models(train, test, cols, target_col, horizon=h)
            all_comparison_rows.extend(comparison_rows("rainfall", h, results))

            for model_name in ["RandomForest", "HistGradientBoosting"]:
                r = results[model_name]
                path = save_model(
                    r["model"], "rainfall", model_name, h, cols, r["metrics"],
                    train_range=[str(train["valid_time"].min()), str(train["valid_time"].max())],
                )
                saved_model_paths.append(path)

            best_name = max(
                ["RandomForest", "HistGradientBoosting"],
                key=lambda n: results[n]["metrics"].get("F1", 0),
            )
            m = results[best_name]["metrics"]
            forecast_results["rainfall"][h] = {"best_model": best_name, **m}
            pos_rate = test[target_col].mean()
            print(f"  h={h:>2}h  test positive rate={pos_rate:.3f}  "
                  f"RandomForest F1={results['RandomForest']['metrics']['F1']:.4f}  "
                  f"HistGB F1={results['HistGradientBoosting']['metrics']['F1']:.4f}  "
                  f"(train={len(train)}, test={len(test)})")

    # ---- Save comparison table + forecast results -----------------------------
    print_section("Saving outputs")
    comp_df = pd.DataFrame(all_comparison_rows)
    comp_csv = DATA_PHASE4B_DIR / "model_comparison.csv"
    comp_json = DATA_PHASE4B_DIR / "model_comparison.json"
    comp_df.to_csv(comp_csv, index=False)
    comp_df.to_json(comp_json, orient="records", indent=2)
    print(f"  {comp_csv}\n  {comp_json}")

    forecast_json = DATA_PHASE4B_DIR / "forecast_results.json"
    with open(forecast_json, "w") as f:
        json.dump(forecast_results, f, indent=2, default=str)
    print(f"  {forecast_json}")

    metrics_json = DATA_PHASE4B_DIR / "metrics.json"
    with open(metrics_json, "w") as f:
        json.dump({
            "phase1_baseline_1h_temperature": PHASE1_BASELINE_1H,
            "phase4b_1h_temperature_random_forest": {k: rf_1h[k] for k in ["MAE", "RMSE", "R2"]},
            "phase4b_1h_temperature_histgb": {k: hgb_1h[k] for k in ["MAE", "RMSE", "R2"]},
            "n_models_saved": len(saved_model_paths),
            "horizons": HORIZONS,
        }, f, indent=2, default=str)
    print(f"  {metrics_json}")
    print(f"  Saved {len(saved_model_paths)} model files under models/phase4b/")

    # ---- Phase 4A integration (Part H) -----------------------------------------
    print_section("Phase 4A WeatherIntelligence integration (backward-compatible)")
    try:
        existing_records = load_weather_intelligence_json()  # real Phase 4A output, unmodified on disk
    except FileNotFoundError:
        existing_records = []

    integrated = []
    if existing_records:
        # Phase 4A's own WeatherIntelligence.timestamp is stored as an
        # ISO-8601 string with a trailing "Z" and a "T" separator (e.g.
        # "2024-01-01T00:00:00Z", see data/phase4/weather_intelligence.json),
        # while the real cleaned dataset's valid_time column uses
        # "YYYY-MM-DD HH:MM:SS" (see data/processed/jabalpur_clean.csv).
        # Both refer to the exact same real timestamps -- this normalises
        # the format for matching only, it does not change either file.
        def _normalize_ts(ts):
            return ts.replace("T", " ").replace("Z", "").strip() if ts else ts

        feat_all = build_temperature_feature_set(raw, horizon=1)
        feat_all_ts_norm = feat_all["valid_time"].astype(str)

        from phase4b.intelligence_integration import predict_multi_horizon

        for wi in existing_records:
            norm_ts = _normalize_ts(wi.timestamp)
            match = feat_all[feat_all_ts_norm == norm_ts]
            if len(match):
                row = match.iloc[0]
                temp_preds, rain_preds = predict_multi_horizon(row, HORIZONS)
                forecast = build_forecast_field(temp_preds, rain_preds, HORIZONS)
                wi = attach_phase4b_forecast(wi, forecast)
                integrated.append(wi)
                print(f"  Attached real Phase 4B forecast to WeatherIntelligence record {wi.id} "
                      f"(timestamp={wi.timestamp})")
            else:
                print(f"  Skipped record {wi.id} (timestamp={wi.timestamp}): not present in the "
                      f"h=1 leakage-safe feature set (insufficient lag history before it, or "
                      f"outside the real dataset's 2024-01-01..2025-12-31 range).")

        if integrated:
            out_path = DATA_PHASE4B_DIR / "weather_intelligence_with_forecast.json"
            with open(out_path, "w") as f:
                json.dump([r.to_dict() for r in integrated], f, indent=2, default=str)
            print(f"  Saved {len(integrated)} integrated record(s) to {out_path} "
                  f"(data/phase4/weather_intelligence.json itself is untouched)")
        else:
            print("  No Phase 4A record's timestamp matched the real dataset -- nothing integrated, "
                  "nothing fabricated.")
    else:
        print("  No existing Phase 4A records found at data/phase4/weather_intelligence.json -- skipped.")

    print_section("Known limitations, stated plainly")
    print(
        "- Phase 4B's feature set (wider lag/rolling columns, see feature_engineering.py) differs\n"
        "  from Phase 1's narrower notebook-05 feature set, so the 1h comparison above is honest but\n"
        "  not a strictly like-for-like ablation of 'more horizons, same features'.\n"
        "- Single grid point (Jabalpur, ERA5 only) -- same scope limitation Phase 1 documented.\n"
        "- Rainfall classification at longer horizons (12h, 24h) trains on a lower effective sample\n"
        "  count once dropna() removes rows without a full lag/rolling history plus a full horizon\n"
        "  shift; see Train_samples/Test_samples in model_comparison.csv for the exact counts.\n"
        "- HistGradientBoosting was run with default/lightly-set hyperparameters (max_iter=200,\n"
        "  random_state=42) -- no extensive hyperparameter search was performed for this SIH demo.\n"
        "- forecast.rainfall_probability is a model-predicted class probability, not a calibrated\n"
        "  probability of truth; forecast.is_real_time is always False (batch, historical-data model)."
    )


if __name__ == "__main__":
    main()
