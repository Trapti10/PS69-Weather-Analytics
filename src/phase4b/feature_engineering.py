"""
Phase 4B -- Feature engineering for the advanced multi-horizon ML layer.

This module does NOT replace Phase 1's feature pipeline
(`src/features/build_features.py`). It REUSES Phase 1's own,
already-tested primitives --

    add_cyclical_time_features()
    add_lag_features()
    add_rolling_features()
    add_target_temperature()

-- unmodified, and only adds what Phase 1 did not need: (a) a wider set of
lag/rolling source columns, (b) multi-horizon temperature targets built by
calling Phase 1's own `add_target_temperature(df, horizon=h)` once per
horizon, and (c) a multi-horizon rain-occurrence target, following the exact
same shift(-h) pattern Phase 1 used for `target_rain_next1h` in notebook 04
(`feat_rain['target_rain_next1h'] = feat_rain['rain_flag'].shift(-1)`), just
generalised to h in {1, 3, 6, 12, 24}.

*** LEAKAGE-PREVENTION RULE (stated explicitly, per project requirement) ***
For a prediction made at time t for horizon h (i.e. predicting the value at
t+h):

  - Every FEATURE column is computed using only observations at time <= t.
    Concretely: lag features use `.shift(lag)` with lag >= 1 (past values
    only), and rolling features use `.shift(1).rolling(window).agg()` --
    the `.shift(1)` BEFORE the rolling window means the row at time t never
    includes its own value or any value after it in the rolling window.
    Cyclical hour/day-of-year features are deterministic functions of the
    row's own timestamp, not of any weather observation, so they carry no
    leakage risk.
  - Only the TARGET column is allowed to look forward, via `.shift(-h)`,
    and it is never used as a feature -- it is excluded from `feature_cols`
    by every training routine in `time_series_ml.py`.
  - Rows where any lag/rolling feature or the shifted target is NaN
    (the first `max(lag)` rows and the last `h` rows of the series) are
    dropped with `dropna()`, exactly as Phase 1 did -- no imputation that
    could leak information across the boundary.

This rule is identical in spirit to Phase 1's own docstring in
`build_features.py` ("computed causally ... safe to use with chronological
train/test splits without leaking future information"); Phase 4B simply
documents it explicitly and extends it to more columns and more horizons.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from features.build_features import (  # Phase 1's own functions, reused unmodified
    add_cyclical_time_features,
    add_lag_features,
    add_rolling_features,
    add_target_temperature,
    LAG_HOURS,
    ROLL_WINDOWS,
)

# The horizons Phase 4B forecasts at, per the Phase 4B spec (Part C).
HORIZONS = [1, 3, 6, 12, 24]

# Phase 1 only lagged/rolled a subset of columns (t2m_c, msl_hpa, wind_speed,
# d2m_c for lags; t2m_c, msl_hpa, tp_mm for rolling). Phase 4B widens this to
# the remaining real weather variables already present in the Phase 1
# cleaned dataset (data/processed/jabalpur_clean.csv) -- relative humidity
# and wind gust -- using the exact same Phase 1 functions, just called with
# a larger `cols` argument. No new column is invented; every name below
# already exists in jabalpur_clean.csv (see src/data/load_clean.py).
PHASE4B_LAG_COLS = ("t2m_c", "msl_hpa", "wind_speed", "d2m_c", "tp_mm",
                     "relative_humidity_approx", "fg10")
PHASE4B_ROLL_COLS = ("t2m_c", "msl_hpa", "tp_mm", "relative_humidity_approx")

NON_FEATURE_COLS = {
    "valid_time", "date", "latitude", "longitude", "u10", "v10",
    "d2m", "t2m", "msl", "tp",  # raw Kelvin/Pa/m fields superseded by the _c/_hpa/_mm versions
}


def _base_features(df: pd.DataFrame) -> pd.DataFrame:
    """Shared causal feature base: cyclical time features + widened
    lag/rolling features, built with Phase 1's own functions unmodified."""
    out = add_cyclical_time_features(df)
    out = add_lag_features(out, cols=PHASE4B_LAG_COLS)
    out = add_rolling_features(out, cols=PHASE4B_ROLL_COLS)
    return out


def build_temperature_feature_set(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Leakage-safe feature set for temperature forecasting at `horizon`
    hours ahead. Target column: target_t2m_h{horizon} (Phase 1's own
    naming convention, from add_target_temperature())."""
    out = _base_features(df)
    out = add_target_temperature(out, horizon=horizon)
    out = out.dropna().reset_index(drop=True)
    return out


def build_rainfall_feature_set(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Leakage-safe feature set for rain-occurrence classification at
    `horizon` hours ahead. Target column: target_rain_next{horizon}h,
    generalising Phase 1's own notebook-04 pattern
    (`rain_flag.shift(-1)` -> `target_rain_next1h`) to h in HORIZONS.
    Uses Phase 1's own rain_flag column (tp_mm > 0.1, see
    src/data/load_clean.py) unmodified -- the threshold is preserved."""
    out = _base_features(df)
    target_col = f"target_rain_next{horizon}h"
    out[target_col] = out["rain_flag"].shift(-horizon)
    out = out.dropna().reset_index(drop=True)
    out[target_col] = out[target_col].astype(int)
    return out


def temperature_feature_columns(df: pd.DataFrame, horizon: int) -> list:
    target_col = f"target_t2m_h{horizon}"
    exclude = NON_FEATURE_COLS | {target_col, "rain_flag"}
    return [c for c in df.columns if c not in exclude and df[c].dtype != "O"]


def rainfall_feature_columns(df: pd.DataFrame, horizon: int) -> list:
    target_col = f"target_rain_next{horizon}h"
    exclude = NON_FEATURE_COLS | {target_col, "rain_flag"}
    return [c for c in df.columns if c not in exclude and df[c].dtype != "O"]
