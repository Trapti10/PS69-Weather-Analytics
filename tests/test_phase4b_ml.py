"""
Phase 4B tests (Part I). Uses small, deterministic synthetic fixtures for
unit tests, per the spec ("Real project data should be used for the actual
demo/evaluation. Do NOT replace real evaluation with synthetic data.") --
these tests never touch data/phase4b/ evaluation outputs; they only check
the Phase 4B code paths in isolation.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from phase4b.feature_engineering import (
    build_temperature_feature_set, build_rainfall_feature_set,
    temperature_feature_columns, rainfall_feature_columns,
    HORIZONS, PHASE4B_LAG_COLS, PHASE4B_ROLL_COLS,
)
from phase4b.time_series_ml import (
    three_way_chronological_split, train_temperature_models,
    train_rainfall_models, comparison_rows,
)
from phase4b.model_persistence import save_model, load_model, MODELS_ROOT
from phase4b.intelligence_integration import build_forecast_field, attach_phase4b_forecast
from phase4.weather_intelligence import WeatherIntelligence
from evaluation.time_series_eval import regression_report, classification_report_dict


N_HOURS = 400  # long enough for lag=24 + horizon=24 + a 3-way chronological split


@pytest.fixture
def synthetic_df():
    """Deterministic synthetic hourly weather series -- NOT real project
    data, used only to exercise Phase 4B code paths in isolation."""
    rng = np.random.default_rng(42)
    idx = pd.date_range("2024-01-01", periods=N_HOURS, freq="h")
    hour = idx.hour.values
    dayofyear = idx.dayofyear.values

    # Deterministic diurnal temperature cycle + tiny fixed noise (seeded).
    t2m_c = 20 + 8 * np.sin(2 * np.pi * (hour - 6) / 24) + rng.normal(0, 0.1, N_HOURS)
    msl_hpa = 1010 + 3 * np.cos(2 * np.pi * hour / 24) + rng.normal(0, 0.05, N_HOURS)
    wind_speed = 2 + 0.5 * np.sin(2 * np.pi * hour / 24) + rng.normal(0, 0.05, N_HOURS)
    d2m_c = t2m_c - 5 + rng.normal(0, 0.1, N_HOURS)
    fg10 = wind_speed + 1.0
    relative_humidity_approx = 70 - 0.5 * (t2m_c - 20) + rng.normal(0, 0.2, N_HOURS)

    # Rainfall: deterministic pulses every ~30 hours so both classes exist.
    tp_mm = np.zeros(N_HOURS)
    tp_mm[::31] = 1.5
    tp_mm[::47] = 0.8
    rain_flag = (tp_mm > 0.1).astype(int)

    df = pd.DataFrame({
        "valid_time": idx.astype(str),
        "t2m_c": t2m_c, "msl_hpa": msl_hpa, "wind_speed": wind_speed,
        "d2m_c": d2m_c, "tp_mm": tp_mm, "fg10": fg10,
        "relative_humidity_approx": relative_humidity_approx,
        "hour": hour, "dayofyear": dayofyear, "rain_flag": rain_flag,
    })
    return df


# 1. Feature generation ------------------------------------------------------

def test_feature_generation_temperature(synthetic_df):
    feat = build_temperature_feature_set(synthetic_df, horizon=1)
    assert "target_t2m_h1" in feat.columns
    assert len(feat) > 0
    for col in PHASE4B_LAG_COLS:
        assert f"{col}_lag1" in feat.columns


def test_feature_generation_rainfall(synthetic_df):
    feat = build_rainfall_feature_set(synthetic_df, horizon=1)
    assert "target_rain_next1h" in feat.columns
    assert set(feat["target_rain_next1h"].unique()) <= {0, 1}


# 2. Lag correctness ----------------------------------------------------------

def test_lag_correctness(synthetic_df):
    feat = build_temperature_feature_set(synthetic_df, horizon=1)
    # Rebuild a lag-1 column manually from the *original* series and compare
    # against the pipeline's own lag1 column, aligned by valid_time.
    manual = synthetic_df.set_index("valid_time")["t2m_c"].shift(1)
    merged = feat.set_index("valid_time")["t2m_c_lag1"]
    common = merged.index.intersection(manual.index)
    assert np.allclose(merged.loc[common].values, manual.loc[common].values, equal_nan=False)


# 3. Rolling correctness -------------------------------------------------------

def test_rolling_correctness(synthetic_df):
    feat = build_temperature_feature_set(synthetic_df, horizon=1)
    manual = synthetic_df["t2m_c"].shift(1).rolling(3).mean()
    manual.index = synthetic_df["valid_time"]
    merged = feat.set_index("valid_time")["t2m_c_rollmean3"]
    common = merged.index.intersection(manual.index)
    assert np.allclose(merged.loc[common].values, manual.loc[common].values, equal_nan=False)


# 4. Chronological splitting ---------------------------------------------------

def test_chronological_split_order(synthetic_df):
    feat = build_temperature_feature_set(synthetic_df, horizon=1)
    train, val, test = three_way_chronological_split(feat)
    assert len(train) + len(val) + len(test) == len(feat)
    assert train["valid_time"].max() <= val["valid_time"].min()
    assert val["valid_time"].max() <= test["valid_time"].min()


# 5. Leakage prevention ---------------------------------------------------------

def test_no_leakage_lag_and_rolling(synthetic_df):
    """A feature value at row i must be identical whether computed on the
    full series or on a truncated series that ends at row i -- i.e. it
    must never depend on any row after i."""
    full_feat = build_temperature_feature_set(synthetic_df, horizon=1)
    cutoff = 200
    truncated = synthetic_df.iloc[:cutoff + 1].reset_index(drop=True)
    trunc_feat = build_temperature_feature_set(truncated, horizon=1)

    row_full = full_feat[full_feat["valid_time"] == synthetic_df["valid_time"].iloc[cutoff - 1]]
    row_trunc = trunc_feat[trunc_feat["valid_time"] == synthetic_df["valid_time"].iloc[cutoff - 1]]
    if len(row_full) and len(row_trunc):
        for col in ["t2m_c_lag1", "t2m_c_lag24", "t2m_c_rollmean3", "msl_hpa_rollstd6"]:
            assert np.isclose(row_full[col].values[0], row_trunc[col].values[0]), col


# 6. Missing-value handling ------------------------------------------------------

def test_missing_value_handling(synthetic_df):
    feat = build_temperature_feature_set(synthetic_df, horizon=24)
    assert not feat.isnull().any().any()
    feat_r = build_rainfall_feature_set(synthetic_df, horizon=24)
    assert not feat_r.isnull().any().any()


# 7. Temperature model training --------------------------------------------------

def test_temperature_model_training(synthetic_df):
    feat = build_temperature_feature_set(synthetic_df, horizon=1)
    train, val, test = three_way_chronological_split(feat)
    cols = temperature_feature_columns(feat, horizon=1)
    results = train_temperature_models(train, test, cols, "target_t2m_h1", horizon=1)
    assert set(["NaivePersistence", "RandomForest", "HistGradientBoosting"]) <= set(results.keys())
    for name in ["RandomForest", "HistGradientBoosting"]:
        assert "MAE" in results[name]["metrics"]
        assert results[name]["model"] is not None


# 8. Rainfall model training -------------------------------------------------------

def test_rainfall_model_training(synthetic_df):
    feat = build_rainfall_feature_set(synthetic_df, horizon=1)
    train, val, test = three_way_chronological_split(feat)
    cols = rainfall_feature_columns(feat, horizon=1)
    results = train_rainfall_models(train, test, cols, "target_rain_next1h", horizon=1)
    for name in ["RandomForest", "HistGradientBoosting"]:
        assert "Precision" in results[name]["metrics"]
        assert "Recall" in results[name]["metrics"]
        assert "F1" in results[name]["metrics"]


# 9. Multi-horizon support --------------------------------------------------------

def test_multi_horizon_targets_differ(synthetic_df):
    targets = {}
    for h in HORIZONS:
        feat = build_temperature_feature_set(synthetic_df, horizon=h)
        targets[h] = feat[f"target_t2m_h{h}"].values[:5]
    # Different horizons should generally produce different target arrays.
    assert not np.allclose(targets[1], targets[24])


# 10. Metric calculation ------------------------------------------------------------

def test_metric_calculation_perfect_prediction():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    report = regression_report(y, y)
    assert report["MAE"] == 0
    assert report["RMSE"] == 0
    assert report["R2"] == 1

    y_c = np.array([0, 1, 1, 0])
    creport = classification_report_dict(y_c, y_c, y_c)
    assert creport["Precision"] == 1
    assert creport["Recall"] == 1
    assert creport["F1"] == 1


# 11 & 12. Model persistence + reload ------------------------------------------------

def test_model_persistence_and_reload(synthetic_df, tmp_path, monkeypatch):
    feat = build_temperature_feature_set(synthetic_df, horizon=1)
    train, val, test = three_way_chronological_split(feat)
    cols = temperature_feature_columns(feat, horizon=1)
    results = train_temperature_models(train, test, cols, "target_t2m_h1", horizon=1)

    import phase4b.model_persistence as mp
    monkeypatch.setattr(mp, "MODELS_ROOT", tmp_path / "phase4b")

    model = results["RandomForest"]["model"]
    metrics = results["RandomForest"]["metrics"]
    path = mp.save_model(model, "temperature", "RandomForest", 1, cols, metrics)
    assert path.exists()

    loaded_model, meta = mp.load_model("temperature", "RandomForest", 1)
    assert meta["horizon_hours"] == 1
    assert meta["feature_list"] == cols

    preds_original = model.predict(test[cols])
    preds_loaded = loaded_model.predict(test[cols])
    assert np.allclose(preds_original, preds_loaded)


# 13. Reproducibility --------------------------------------------------------------

def test_reproducibility(synthetic_df):
    feat = build_temperature_feature_set(synthetic_df, horizon=1)
    train, val, test = three_way_chronological_split(feat)
    cols = temperature_feature_columns(feat, horizon=1)

    results_a = train_temperature_models(train, test, cols, "target_t2m_h1", horizon=1)
    results_b = train_temperature_models(train, test, cols, "target_t2m_h1", horizon=1)

    preds_a = results_a["RandomForest"]["model"].predict(test[cols])
    preds_b = results_b["RandomForest"]["model"].predict(test[cols])
    assert np.allclose(preds_a, preds_b)


# 14. Phase 4A compatibility -------------------------------------------------------

def test_phase4a_compatibility_forecast_field():
    wi = WeatherIntelligence(timestamp="2024-01-01T00:00:00Z", latitude=23.25, longitude=80.0)
    assert wi.forecast is None  # Phase 4A default, unchanged

    forecast = build_forecast_field(
        temperature_predictions={1: 25.3, 24: 27.1},
        rainfall_predictions={1: 0.05, 24: 0.12},
        horizons=[1, 24],
    )
    wi = attach_phase4b_forecast(wi, forecast)
    assert wi.forecast["temperature_forecast_c"]["1"] == 25.3
    assert wi.forecast["is_real_time"] is False

    # Round-trip through to_dict/from_dict (Phase 4A's own methods,
    # unmodified) must still work with a populated forecast field.
    round_tripped = WeatherIntelligence.from_dict(wi.to_dict())
    assert round_tripped.forecast["rainfall_probability"]["24"] == 0.12
    assert round_tripped.overall_confidence == wi.overall_confidence
