"""
ERA5 adapter — converts rows from the Phase-1 ERA5 CSV into the common
WeatherRecord schema (src/schemas/weather_record.py). This is Phase 2B's
"Source 1" connector, parallel to the existing Phase-2A IMD connector.

UNIT CONVERSIONS (documented explicitly, never silent):
- t2m, d2m: ERA5 native unit is KELVIN -> converted to Celsius: C = K - 273.15
- msl:      ERA5 native unit is PASCAL -> converted to hPa:    hPa = Pa / 100
- tp:       ERA5 native unit is METRES (hourly accumulation) -> converted to mm: mm = m * 1000
- u10, v10: ERA5 native unit is m/s already -> wind_speed = sqrt(u10^2 + v10^2), no conversion
- fg10:     ERA5 native unit is m/s already (wind gust) -> stored in raw_payload, not currently
            a WeatherRecord field (schema has no gust field yet)

These are the same conversions already used in Phase 1's
src/data/load_clean.py::clean_and_convert -- reproduced here (not imported)
because Phase 1's function returns a full pandas pipeline with derived
columns for the notebooks, while this adapter needs to emit WeatherRecord
objects one row at a time. Keeping the constants identical is what matters;
duplicating the plumbing keeps Phase 1 and Phase 2B independently readable.
"""
from __future__ import annotations

import sys
import zipfile
import io
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_record import WeatherRecord
from ingestion.validators import validate_record  # reuse Phase-2A range checks, don't duplicate

KELVIN_OFFSET = 273.15
PASCAL_TO_HPA = 100.0
METRES_TO_MM = 1000.0

# ERA5 is a MODEL reanalysis, not a direct ground observation -- given a lower
# base confidence than IMD's default (0.9). This is a stated, documented
# assumption for this project, not a measured meteorological fact.
ERA5_BASE_CONFIDENCE = 0.85


def load_era5_raw(path: str) -> pd.DataFrame:
    """Load the ERA5 CSV, transparently unzipping if it's a Copernicus CDS
    zip archive saved with a .csv extension (same detection as Phase 1)."""
    with open(path, "rb") as f:
        head = f.read(4)
    if head[:2] == b"PK":
        with zipfile.ZipFile(path) as zf:
            inner_name = zf.namelist()[0]
            with zf.open(inner_name) as inner:
                return pd.read_csv(io.BytesIO(inner.read()))
    return pd.read_csv(path)


def _row_to_record(row: pd.Series) -> WeatherRecord:
    """Convert one raw ERA5 row (native units) into a standardized WeatherRecord."""
    temperature_c = round(float(row["t2m"]) - KELVIN_OFFSET, 3)
    pressure_hpa = round(float(row["msl"]) / PASCAL_TO_HPA, 3)
    rainfall_mm = round(float(row["tp"]) * METRES_TO_MM, 4)
    wind_speed_ms = round(float(np.sqrt(row["u10"] ** 2 + row["v10"] ** 2)), 3)
    wind_dir_deg = round(float((np.degrees(np.arctan2(row["u10"], row["v10"])) + 360) % 360), 2)

    timestamp = pd.to_datetime(row["valid_time"]).strftime("%Y-%m-%dT%H:%M:%SZ")

    record = WeatherRecord(
        source="ERA5",
        station_id=None,  # ERA5 is a reanalysis grid point, not a physical station
        timestamp=timestamp,
        country="India",
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        temperature=temperature_c,
        humidity=None,  # ERA5 single-levels-timeseries export used in Phase 1 has no RH field
        pressure=pressure_hpa,
        rainfall=rainfall_mm,
        wind_speed=wind_speed_ms,
        wind_direction=wind_dir_deg,
        event_type="reanalysis_gridpoint",
        description="ERA5 hourly reanalysis (Copernicus CDS)",
        raw_payload={
            "valid_time": str(row["valid_time"]),
            "u10": float(row["u10"]), "v10": float(row["v10"]),
            "fg10": float(row["fg10"]) if "fg10" in row and pd.notna(row["fg10"]) else None,
            "d2m": float(row["d2m"]), "t2m": float(row["t2m"]),
            "msl": float(row["msl"]), "tp": float(row["tp"]),
            "latitude": float(row["latitude"]), "longitude": float(row["longitude"]),
        },
    )
    # Reuse the SAME range-check/flagging logic as IMD (Phase 2A) -- only the
    # base confidence differs, because ERA5 is a model reanalysis, not a
    # direct ground observation. See ERA5_BASE_CONFIDENCE comment above.
    return validate_record(record, base_confidence=ERA5_BASE_CONFIDENCE)


def era5_csv_to_records(path: str, limit: int = None) -> List[WeatherRecord]:
    """Load the ERA5 CSV and convert rows to WeatherRecords.
    `limit`: optional cap on number of rows (useful for demo/testing; None = all rows)."""
    df = load_era5_raw(path)
    if limit is not None:
        df = df.head(limit)
    return [_row_to_record(row) for _, row in df.iterrows()]
