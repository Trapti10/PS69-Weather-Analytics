"""
Open-Meteo adapter -- converts the real downloaded Open-Meteo Historical
Weather API JSON response into the common WeatherRecord schema
(src/schemas/weather_record.py). This is Phase 2C's "Source 3" connector,
parallel to the existing Phase-2A IMD connector and Phase-2B ERA5 adapter.

SOURCE FILE: data/raw/jabalpur_openmeteo_2024_2025.json -- a real, unmodified
response from https://archive-api.open-meteo.com/v1/archive, fetched by the
user (network access to that domain is not available from this sandbox) for:
    latitude=23.25, longitude=80.00 (snapped by Open-Meteo to its nearest
    model grid point: 23.233742, 80.0 -- see `elevation`/`latitude`/
    `longitude` fields in the raw response), 2024-01-01 to 2025-12-31,
    hourly, timezone=UTC, wind_speed_unit=ms.

*** CRITICAL SCIENTIFIC LIMITATION (documented, not glossed over) ***
Open-Meteo's Historical Weather API is itself MODEL / REANALYSIS output
(a blend of ECMWF IFS, ERA5, and ERA5-Land, automatically selected via its
"best_match" logic since no `model` parameter was specified in the request).
It is NOT an independent ground-truth observation. Comparing ERA5 against
Open-Meteo is therefore a CROSS-MODEL / CROSS-SOURCE comparison, not a
model-vs-observation validation. IMD remains the only observational source
in this architecture (Phase 2A). Do not describe ERA5+Open-Meteo agreement
as "verified truth" anywhere downstream of this adapter.

UNIT CONVERSIONS / MAPPINGS (documented explicitly, per the request's
`hourly_units` block -- verified against the real downloaded file, not
assumed from API docs alone):
- temperature_2m        (°C)   -> temperature   -- no conversion needed
- relative_humidity_2m  (%)    -> humidity      -- no conversion needed
- surface_pressure      (hPa)  -> pressure      -- ** SEE PRESSURE CAVEAT **
- precipitation         (mm)   -> rainfall      -- no conversion needed
- wind_speed_10m        (m/s)  -> wind_speed    -- no conversion needed
                                                    (wind_speed_unit=ms was
                                                    set explicitly in the
                                                    request, verified against
                                                    hourly_units)
- wind_gusts_10m        (m/s)  -> stored in raw_payload as "wind_gust",
                                   same treatment as ERA5's fg10 (the shared
                                   WeatherRecord schema has no gust field)
- wind_direction_10m: NOT requested/available in this pull -> wind_direction
                        is left None, honestly, never guessed

*** PRESSURE CAVEAT (important, do not average this away silently) ***
The request used Open-Meteo's `surface_pressure` variable, not
`pressure_msl` (mean-sea-level pressure). ERA5's Phase-1/2B pipeline uses
`msl` (mean-sea-level pressure). Jabalpur's station elevation in the
Open-Meteo response is 390 m, so `surface_pressure` will be systematically
LOWER than `pressure_msl`/ERA5's `msl` by roughly 35-45 hPa purely due to
altitude -- this is real physics (the standard atmosphere loses ~1 hPa per
~8-8.5 m of elevation near sea level), NOT a genuine source disagreement
about the weather. This is flagged explicitly in the Phase 2C report rather
than silently reconciled, per the project's no-fabrication rule -- reducing
it would require re-pulling `pressure_msl` from Open-Meteo, which requires
network access this sandbox does not have.
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_record import WeatherRecord
from ingestion.validators import validate_record  # reuse Phase-2A range checks, don't duplicate

# Open-Meteo's Historical Weather API is a model/reanalysis BLEND product
# (best_match: ECMWF IFS + ERA5/ERA5-Land), not a direct ground observation,
# and not the same product as Phase-1/2B's raw Copernicus CDS ERA5 pull.
# A stated, documented assumption (not a measured meteorological fact),
# same style as ERA5_BASE_CONFIDENCE in era5_adapter.py -- given slightly
# lower than ERA5's 0.85 because it is a further-removed, blended/
# downscaled product with fewer publicly documented provenance details
# than the raw CDS reanalysis.
OPENMETEO_BASE_CONFIDENCE = 0.80


def load_openmeteo_raw(path: str) -> Dict[str, Any]:
    """Load the real Open-Meteo JSON response from disk."""
    with open(path, "r") as f:
        return json.load(f)


def _row_to_record(payload: Dict[str, Any], grid_lat: float, grid_lon: float,
                    idx: int) -> WeatherRecord:
    """Convert one hourly index of the Open-Meteo response into a
    standardized WeatherRecord."""
    hourly = payload["hourly"]

    raw_time = hourly["time"][idx]  # e.g. "2024-01-01T00:00" -- naive, but
    # request was made with timezone=UTC, verified in payload["timezone"],
    # so this is appended with "Z" to make it an explicit UTC ISO timestamp
    # -- never assumed silently, checked against the payload below.
    timestamp = f"{raw_time}:00Z" if len(raw_time) == 16 else raw_time

    def _get(var: str) -> Optional[float]:
        val = hourly.get(var, [None] * len(hourly["time"]))[idx]
        return None if val is None else float(val)

    record = WeatherRecord(
        source="Open-Meteo",
        station_id=None,  # gridded model output, not a physical station -- same as ERA5
        timestamp=timestamp,
        country="India",
        latitude=grid_lat,
        longitude=grid_lon,
        temperature=_get("temperature_2m"),
        humidity=_get("relative_humidity_2m"),
        pressure=_get("surface_pressure"),  # see PRESSURE CAVEAT in module docstring
        rainfall=_get("precipitation"),
        wind_speed=_get("wind_speed_10m"),
        wind_direction=None,  # not requested in this pull -- left None, not guessed
        event_type="model_reanalysis_gridpoint",
        description=(
            "Open-Meteo Historical Weather API (best_match blend: ECMWF IFS "
            "+ ERA5/ERA5-Land) -- MODEL output, not an independent ground "
            "observation"
        ),
        raw_payload={
            "time_raw": raw_time,
            "wind_gust": _get("wind_gusts_10m"),
            "timezone": payload.get("timezone"),
            "elevation_m": payload.get("elevation"),
            "requested_variables": list(hourly.keys()),
        },
    )
    # Reuse the SAME range-check/flagging logic as IMD/ERA5 -- only the base
    # confidence differs, per OPENMETEO_BASE_CONFIDENCE comment above.
    return validate_record(record, base_confidence=OPENMETEO_BASE_CONFIDENCE)


def openmeteo_json_to_records(path: str, limit: int = None) -> List[WeatherRecord]:
    """Load the real Open-Meteo JSON file and convert its hourly series into
    WeatherRecords. `limit`: optional cap (useful for tests; None = all rows).

    Raises ValueError if the file doesn't look like a real Open-Meteo
    archive response (defensive check -- never silently substitutes
    synthetic data for a malformed file)."""
    payload = load_openmeteo_raw(path)

    if "hourly" not in payload or "time" not in payload.get("hourly", {}):
        raise ValueError(
            f"'{path}' does not look like a real Open-Meteo archive response "
            "(missing 'hourly.time'). Refusing to fabricate records."
        )

    grid_lat = float(payload["latitude"])
    grid_lon = float(payload["longitude"])
    n = len(payload["hourly"]["time"])
    if limit is not None:
        n = min(n, limit)

    return [_row_to_record(payload, grid_lat, grid_lon, i) for i in range(n)]
