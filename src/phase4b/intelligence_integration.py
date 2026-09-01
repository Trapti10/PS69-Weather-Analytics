"""
Phase 4B -- integration into Phase 4A's WeatherIntelligence layer (Part H).

Phase 4A's `WeatherIntelligence.forecast` field was explicitly defined but
deliberately left unpopulated ("the `forecast` field exists so a LATER
phase has a place to put results -- Phase 4A never populates it", see
src/phase4/weather_intelligence.py). Phase 4B is that later phase.

This module does NOT redesign WeatherIntelligence, its builder function,
or its storage format -- it only fills in the pre-existing `forecast`
field on an already-built WeatherIntelligence record, using real Phase 4B
model predictions. Every other field is left untouched.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from phase4.weather_intelligence import WeatherIntelligence  # reused unmodified
from phase4b.model_persistence import load_model

FORECAST_MODEL_NAME = "HistGradientBoosting"  # the Phase 4B advanced model used for serving


def build_forecast_field(
    temperature_predictions: Dict[int, float],
    rainfall_predictions: Dict[int, float],
    horizons: List[int],
    model_name: str = FORECAST_MODEL_NAME,
) -> Dict[str, Any]:
    """Assembles the `forecast` dict, explicit about what it is and is not.

    NOT claimed:
      - real-time (these are batch predictions from a saved Phase 4B model,
        not a live streaming forecast)
      - a probability of truth (rainfall probabilities are the classifier's
        predicted probability of the positive class, i.e. model confidence,
        not a guarantee)
      - perfect (see `evaluation_metrics` recorded alongside each saved
        model in models/phase4b/*/*.json for honest, measured performance)
    """
    return {
        "source": "Phase 4B advanced ML layer",
        "model_used": model_name,
        "horizons_hours": horizons,
        "temperature_forecast_c": {str(h): temperature_predictions.get(h) for h in horizons},
        "rainfall_probability": {str(h): rainfall_predictions.get(h) for h in horizons},
        "is_real_time": False,
        "disclaimer": (
            "Batch forecast from a saved Phase 4B model, evaluated on historical "
            "held-out data (see models/phase4b/*/*.json for metrics). "
            "rainfall_probability is model-predicted class probability, not a "
            "probability of truth. Not a real-time forecast."
        ),
    }


def attach_phase4b_forecast(wi: WeatherIntelligence, forecast: Dict[str, Any]) -> WeatherIntelligence:
    """Populates the pre-existing (previously-None) `forecast` field on an
    already-built WeatherIntelligence record. Backward compatible: every
    other field, and the shape of WeatherIntelligence itself, is unchanged.
    A record with forecast=None (e.g. any Phase 4A-era record) remains
    perfectly valid and loadable -- this is purely additive."""
    wi.forecast = forecast
    return wi


def predict_multi_horizon(feature_row, horizons: List[int]):
    """Loads saved Phase 4B models for each horizon and predicts for a
    single feature row (a pandas Series or one-row DataFrame's iloc[0]).
    Returns (temperature_predictions, rainfall_predictions) dicts keyed by
    horizon. Horizons whose model failed to load are simply omitted
    (never fabricated)."""
    import pandas as pd

    temp_preds: Dict[int, float] = {}
    rain_preds: Dict[int, float] = {}

    for h in horizons:
        try:
            model, meta = load_model("temperature", FORECAST_MODEL_NAME, h)
            cols = meta["feature_list"]
            X = pd.DataFrame([feature_row[cols].values], columns=cols)
            temp_preds[h] = float(model.predict(X)[0])
        except (FileNotFoundError, KeyError):
            continue

        try:
            model, meta = load_model("rainfall", FORECAST_MODEL_NAME, h)
            cols = meta["feature_list"]
            X = pd.DataFrame([feature_row[cols].values], columns=cols)
            rain_preds[h] = float(model.predict_proba(X)[0, 1])
        except (FileNotFoundError, KeyError):
            continue

    return temp_preds, rain_preds
