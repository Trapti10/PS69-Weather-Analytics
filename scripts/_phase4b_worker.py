#!/usr/bin/env python3
"""
Internal Phase 4B worker: trains + evaluates + saves models for ONE
target/horizon combination, on the real cleaned dataset, and appends its
comparison rows to data/phase4b/_partial_comparison.jsonl.

This file exists purely as an execution-time workaround (fitting real
17,544-row training runs within tool call time limits) -- it uses the
exact same src/phase4b/* functions run_phase4b_demo.py uses, with no
different logic, no different data, and no different hyperparameters.
run_phase4b_demo.py's own aggregation step (not this file) produces the
final data/phase4b/ outputs and README numbers.

Usage: python3 scripts/_phase4b_worker.py <temperature|rainfall> <horizon>
"""
import sys
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from phase4b.feature_engineering import (
    build_temperature_feature_set, build_rainfall_feature_set,
    temperature_feature_columns, rainfall_feature_columns,
)
from phase4b.time_series_ml import (
    three_way_chronological_split, train_temperature_models,
    train_rainfall_models, comparison_rows,
)
from phase4b.model_persistence import save_model

DATA_PHASE4B_DIR = PROJECT_ROOT / "data" / "phase4b"
DATA_PHASE4B_DIR.mkdir(parents=True, exist_ok=True)
PARTIAL_PATH = DATA_PHASE4B_DIR / "_partial_comparison.jsonl"


def main():
    target = sys.argv[1]
    horizon = int(sys.argv[2])
    assert target in ("temperature", "rainfall")

    raw = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "jabalpur_clean.csv")

    if target == "temperature":
        feat = build_temperature_feature_set(raw, horizon=horizon)
        train, val, test = three_way_chronological_split(feat)
        cols = temperature_feature_columns(feat, horizon=horizon)
        target_col = f"target_t2m_h{horizon}"
        results = train_temperature_models(train, test, cols, target_col, horizon=horizon)
    else:
        feat = build_rainfall_feature_set(raw, horizon=horizon)
        train, val, test = three_way_chronological_split(feat)
        cols = rainfall_feature_columns(feat, horizon=horizon)
        target_col = f"target_rain_next{horizon}h"
        results = train_rainfall_models(train, test, cols, target_col, horizon=horizon)

    rows = comparison_rows(target, horizon, results)

    for model_name in ["RandomForest", "HistGradientBoosting"]:
        r = results[model_name]
        save_model(
            r["model"], target, model_name, horizon, cols, r["metrics"],
            train_range=[str(train["valid_time"].min()), str(train["valid_time"].max())],
        )

    with open(PARTIAL_PATH, "a") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")

    print(f"[{target} h={horizon}] done. train={len(train)} test={len(test)}")
    for name, r in results.items():
        print(f"  {name}: {r['metrics']}")


if __name__ == "__main__":
    main()
