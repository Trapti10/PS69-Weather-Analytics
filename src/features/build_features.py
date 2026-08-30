"""
Feature engineering for time-series ML on the Jabalpur ERA5 dataset.

All lag/rolling features are computed causally (using only past values)
so they are safe to use with chronological train/test splits without
leaking future information.
"""
import numpy as np
import pandas as pd

LAG_HOURS = [1, 2, 3, 6, 12, 24]
ROLL_WINDOWS = [3, 6, 24]


def add_cyclical_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["doy_sin"] = np.sin(2 * np.pi * df["dayofyear"] / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * df["dayofyear"] / 365.25)
    return df


def add_lag_features(df: pd.DataFrame, cols=("t2m_c", "msl_hpa", "wind_speed", "d2m_c")) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        for lag in LAG_HOURS:
            df[f"{col}_lag{lag}"] = df[col].shift(lag)
    return df


def add_rolling_features(df: pd.DataFrame, cols=("t2m_c", "msl_hpa", "tp_mm")) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        for w in ROLL_WINDOWS:
            df[f"{col}_rollmean{w}"] = df[col].shift(1).rolling(w).mean()
            df[f"{col}_rollstd{w}"] = df[col].shift(1).rolling(w).std()
    return df


def add_target_temperature(df: pd.DataFrame, horizon: int = 1) -> pd.DataFrame:
    """Target = t2m_c `horizon` hours ahead (shift backwards -> future value on current row)."""
    df = df.copy()
    df[f"target_t2m_h{horizon}"] = df["t2m_c"].shift(-horizon)
    return df


def build_feature_set(df: pd.DataFrame, horizon: int = 1) -> pd.DataFrame:
    """Full feature pipeline used by notebook 04 / 05."""
    out = add_cyclical_time_features(df)
    out = add_lag_features(out)
    out = add_rolling_features(out)
    out = add_target_temperature(out, horizon=horizon)
    out = out.dropna().reset_index(drop=True)
    return out
