"""
Phase 4B -- advanced ML training, multi-horizon evaluation, and model
comparison. Builds ON TOP of Phase 1's baseline ML rather than replacing
it: chronological splitting and metric computation reuse Phase 1's own
`src/evaluation/time_series_eval.py` (chronological_split, regression_report,
classification_report_dict) unmodified.

Two models are compared per target/horizon, per the Phase 4B spec (Part C):
  - "RandomForest"          -- same family Phase 1 used, kept as the
                                 in-family baseline model for Phase 4B.
  - "HistGradientBoosting"  -- the advanced model Phase 4B adds.

Validation strategy (Part E): TRAIN -> VALIDATION -> TEST, chronological,
via Phase 1's own `chronological_split(train_frac=0.7, val_frac=0.15)`.
The validation split is produced and reported but only the TEST split is
used for the headline evaluation metrics below (identical to Phase 1's
own methodology, which also reported final numbers on the test split);
this avoids silently changing Phase 1's methodology (rule 15) while still
using a real three-way split.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    RandomForestRegressor, RandomForestClassifier,
    HistGradientBoostingRegressor, HistGradientBoostingClassifier,
)

sys.path.append(str(Path(__file__).resolve().parents[1]))
from evaluation.time_series_eval import (  # Phase 1's own module, reused unmodified
    chronological_split, regression_report, classification_report_dict,
    naive_persistence_baseline,
)

RANDOM_SEED = 42  # same seed Phase 1 used, for comparability


def three_way_chronological_split(df: pd.DataFrame, time_col: str = "valid_time"):
    """TRAIN -> VALIDATION -> TEST, chronological (Part E). Thin wrapper
    documenting the split explicitly; the actual splitting logic is
    Phase 1's own `chronological_split`, called with the same
    train_frac/val_frac Phase 1's notebook 05 used (0.7 / 0.15), never a
    random `train_test_split`."""
    return chronological_split(df, time_col=time_col, train_frac=0.7, val_frac=0.15)


# ---------------------------------------------------------------------------
# Temperature (regression) models
# ---------------------------------------------------------------------------

def train_temperature_models(train: pd.DataFrame, test: pd.DataFrame,
                              feature_cols: List[str], target_col: str,
                              horizon: int) -> Dict[str, dict]:
    """Fits RandomForest + HistGradientBoosting for one horizon, evaluates
    both on the (held-out, future-only) test split with Phase 1's own
    regression_report(), and includes the naive-persistence baseline
    (t+h predicted as equal to t) for honest comparison. Returns a dict
    keyed by model name -> {metrics, fitted_model, n_train, n_test}."""
    X_train, y_train = train[feature_cols], train[target_col]
    X_test, y_test = test[feature_cols], test[target_col]

    results = {}

    # Naive persistence baseline, generalised to horizon h: predict that
    # the value h hours ahead equals the current t2m_c (Phase 1's own
    # naive_persistence_baseline(), unmodified, feature_col='t2m_c').
    naive_metrics = naive_persistence_baseline(test, target_col=target_col, feature_col="t2m_c")
    results["NaivePersistence"] = {
        "metrics": naive_metrics, "model": None,
        "n_train": len(train), "n_test": len(test),
    }

    rf = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=RANDOM_SEED, n_jobs=-1)
    rf.fit(X_train, y_train)
    results["RandomForest"] = {
        "metrics": regression_report(y_test, rf.predict(X_test)),
        "model": rf, "n_train": len(train), "n_test": len(test),
    }

    hgb = HistGradientBoostingRegressor(random_state=RANDOM_SEED, max_iter=200)
    hgb.fit(X_train, y_train)
    results["HistGradientBoosting"] = {
        "metrics": regression_report(y_test, hgb.predict(X_test)),
        "model": hgb, "n_train": len(train), "n_test": len(test),
    }

    return results


# ---------------------------------------------------------------------------
# Rainfall (classification) models
# ---------------------------------------------------------------------------

def train_rainfall_models(train: pd.DataFrame, test: pd.DataFrame,
                           feature_cols: List[str], target_col: str,
                           horizon: int) -> Dict[str, dict]:
    """Fits RandomForest (class_weight='balanced', matching Phase 1's own
    notebook-05 rainfall model exactly) + HistGradientBoostingClassifier
    (imbalance handled via sample_weight, since HGB has no class_weight
    param) for one horizon, evaluated on the held-out test split with
    Phase 1's own classification_report_dict()."""
    X_train, y_train = train[feature_cols], train[target_col]
    X_test, y_test = test[feature_cols], test[target_col]

    results = {}

    naive_pred = np.zeros(len(y_test))
    naive_metrics = classification_report_dict(y_test, naive_pred)
    results["NaiveAlwaysNoRain"] = {
        "metrics": naive_metrics, "model": None,
        "n_train": len(train), "n_test": len(test),
    }

    rf = RandomForestClassifier(n_estimators=300, max_depth=10, class_weight="balanced",
                                 random_state=RANDOM_SEED, n_jobs=-1)
    rf.fit(X_train, y_train)
    proba_rf = rf.predict_proba(X_test)[:, 1]
    pred_rf = (proba_rf >= 0.5).astype(int)
    results["RandomForest"] = {
        "metrics": classification_report_dict(y_test, pred_rf, proba_rf),
        "model": rf, "n_train": len(train), "n_test": len(test),
    }

    pos_rate = y_train.mean()
    if 0 < pos_rate < 1:
        sample_weight = np.where(y_train == 1, 0.5 / pos_rate, 0.5 / (1 - pos_rate))
    else:
        sample_weight = None
    hgb = HistGradientBoostingClassifier(random_state=RANDOM_SEED, max_iter=200)
    hgb.fit(X_train, y_train, sample_weight=sample_weight)
    proba_hgb = hgb.predict_proba(X_test)[:, 1]
    pred_hgb = (proba_hgb >= 0.5).astype(int)
    results["HistGradientBoosting"] = {
        "metrics": classification_report_dict(y_test, pred_hgb, proba_hgb),
        "model": hgb, "n_train": len(train), "n_test": len(test),
    }

    return results


# ---------------------------------------------------------------------------
# Comparison table (Part F)
# ---------------------------------------------------------------------------

def comparison_rows(target_name: str, horizon: int, results: Dict[str, dict]) -> List[dict]:
    """Flattens one horizon's {model_name: {metrics, n_train, n_test}}
    into Part F's comparison-table row schema. Only metrics that actually
    apply to that model/target are populated; everything else is left as
    None rather than fabricated."""
    rows = []
    for model_name, r in results.items():
        m = r["metrics"]
        rows.append({
            "Model": model_name,
            "Target": target_name,
            "Horizon_h": horizon,
            "MAE": m.get("MAE"),
            "RMSE": m.get("RMSE"),
            "R2": m.get("R2"),
            "Precision": m.get("Precision"),
            "Recall": m.get("Recall"),
            "F1": m.get("F1"),
            "ROC_AUC": m.get("ROC_AUC"),
            "Train_samples": r["n_train"],
            "Test_samples": r["n_test"],
        })
    return rows
