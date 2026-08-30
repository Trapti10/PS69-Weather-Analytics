"""
Data loading and cleaning utilities for PS69 Weather Analytics.

The raw file downloaded from Copernicus CDS (ERA5 reanalysis) is a ZIP
archive saved with a .csv extension. This module transparently handles
that, converts ERA5's native units into human-readable units, and
derives a few standard fields used throughout the notebooks.
"""
import zipfile
import io
import numpy as np
import pandas as pd

RAW_PATH = "../data/raw/jabalpur_weather_2024_2025.csv"


def load_raw(path: str = RAW_PATH) -> pd.DataFrame:
    """Load the ERA5 CSV, transparently unzipping if the file is a
    Copernicus CDS zip archive saved with a .csv extension."""
    with open(path, "rb") as f:
        head = f.read(4)

    if head[:2] == b"PK":  # ZIP magic bytes
        with zipfile.ZipFile(path) as zf:
            inner_name = zf.namelist()[0]
            with zf.open(inner_name) as inner:
                df = pd.read_csv(io.BytesIO(inner.read()))
    else:
        df = pd.read_csv(path)

    return df


def clean_and_convert(df: pd.DataFrame) -> pd.DataFrame:
    """Convert ERA5 native units to human-readable units and add
    standard derived columns. Returns a new, sorted, de-duplicated
    DataFrame indexed by a proper datetime column."""
    df = df.copy()
    df["valid_time"] = pd.to_datetime(df["valid_time"])
    df = df.drop_duplicates(subset=["valid_time"]).sort_values("valid_time").reset_index(drop=True)

    # Unit conversions (ERA5 native -> usable units)
    df["t2m_c"] = df["t2m"] - 273.15       # Kelvin -> Celsius
    df["d2m_c"] = df["d2m"] - 273.15       # Kelvin -> Celsius
    df["msl_hpa"] = df["msl"] / 100.0      # Pa -> hPa
    df["tp_mm"] = df["tp"] * 1000.0        # m -> mm

    # Derived features
    df["wind_speed"] = np.sqrt(df["u10"] ** 2 + df["v10"] ** 2)
    df["wind_dir_deg"] = (np.degrees(np.arctan2(df["u10"], df["v10"])) + 360) % 360
    df["relative_humidity_approx"] = 100 * (
        np.exp((17.625 * df["d2m_c"]) / (243.04 + df["d2m_c"]))
        / np.exp((17.625 * df["t2m_c"]) / (243.04 + df["t2m_c"]))
    )

    # Calendar features
    df["hour"] = df["valid_time"].dt.hour
    df["day"] = df["valid_time"].dt.day
    df["month"] = df["valid_time"].dt.month
    df["year"] = df["valid_time"].dt.year
    df["dayofyear"] = df["valid_time"].dt.dayofyear
    df["date"] = df["valid_time"].dt.date

    # Rain occurrence flags (thresholds chosen from EDA, see notebook 03)
    df["rain_flag"] = (df["tp_mm"] > 0.1).astype(int)

    return df


def quality_report(df: pd.DataFrame) -> dict:
    """Return a dict of standard data-quality checks used in notebook 02."""
    expected = pd.date_range(df["valid_time"].min(), df["valid_time"].max(), freq="h")
    missing_times = set(expected) - set(df["valid_time"])
    return {
        "n_rows": len(df),
        "n_cols": df.shape[1],
        "missing_values_per_col": df.isnull().sum().to_dict(),
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_timestamps": int(df.duplicated(subset=["valid_time"]).sum()),
        "expected_hourly_rows": len(expected),
        "actual_rows": len(df),
        "missing_timestamps": len(missing_times),
        "date_range": (str(df["valid_time"].min()), str(df["valid_time"].max())),
        "unique_locations": df[["latitude", "longitude"]].drop_duplicates().to_dict("records"),
    }
