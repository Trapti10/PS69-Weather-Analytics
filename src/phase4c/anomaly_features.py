"""
Phase 4C -- Causal rolling-statistics primitives for anomaly detection.

These are the low-level numeric building blocks `anomaly_detection.py` uses
to score each weather variable. Nothing here knows about WeatherRecord,
sources, or severity -- it only computes rolling statistics over a plain
pandas Series, indexed by time in ascending order, one value per hour (or
whatever the underlying cadence is).

*** CAUSALITY / LEAKAGE-PREVENTION RULE ***
Every rolling statistic used as a baseline for row t is computed from rows
strictly BEFORE t: `series.shift(1).rolling(window, min_periods=...)`. This
is the identical convention Phase 4B's `feature_engineering.py` documents
and uses for its own ML features (".shift(1) BEFORE the rolling window
means the row at time t never includes its own value or any value after
it"). Phase 4C applies the same rule so that "this observation is
anomalous" is always judged against what was known *before* the
observation, not against a window that already contains it.

NaN handling: pandas' `.rolling(..., min_periods=N)` already treats NaN
values inside the window as "not observed" -- it will not compute a
statistic until at least `min_periods` non-NaN values are present in the
window, and NaNs are excluded from the mean/std/quantile calculation
itself. This is exactly the "insufficient history" and "missing value"
behavior Phase 4C needs, so no extra imputation is performed here.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd


def causal_rolling_mean_std(
    series: pd.Series, window: int, min_periods: int
) -> Tuple[pd.Series, pd.Series]:
    """Rolling mean and rolling (sample) standard deviation of `series`,
    computed causally (see module docstring): the value baselined at row i
    uses only rows [i-window, i-1]. Returns (rolling_mean, rolling_std),
    both aligned to `series`'s original index. Rows without `min_periods`
    valid prior observations are NaN in both outputs -- never fabricated.
    """
    shifted = series.shift(1)
    roll = shifted.rolling(window=window, min_periods=min_periods)
    return roll.mean(), roll.std()


def causal_rolling_quantiles(
    series: pd.Series, window: int, min_periods: int, quantiles=(0.5, 0.95)
) -> Tuple[pd.Series, ...]:
    """Rolling quantiles of `series`, computed causally (see module
    docstring). Used for rainfall, whose zero-inflated distribution makes
    an ordinary mean/std z-score misleading (see anomaly_detection.py's
    `detect_rainfall_anomalies` docstring for the full justification).
    Returns one Series per requested quantile, in the given order.
    """
    shifted = series.shift(1)
    roll = shifted.rolling(window=window, min_periods=min_periods)
    return tuple(roll.quantile(q) for q in quantiles)


def safe_zscore(observed: float, baseline_mean: float, baseline_std: float) -> float:
    """Computes (observed - baseline_mean) / baseline_std. Callers MUST
    check for NaN/zero baseline_std themselves before calling this --
    this function assumes it has already been validated, and exists only
    to keep the arithmetic in one documented place."""
    return (observed - baseline_mean) / baseline_std


def is_effectively_zero_variance(std_value: float, epsilon: float) -> bool:
    """True when a rolling standard deviation is too small to divide by
    safely/meaningfully. `epsilon` is an explicit, configurable
    AnomalyConfig field (see anomaly_detection.py) -- never a hidden
    magic number."""
    return (std_value is None) or (not np.isfinite(std_value)) or (std_value < epsilon)
