"""
Validation and standardization: converts raw IMD API responses into
standardized WeatherRecord objects, and applies data-quality checks.

Plausibility ranges are intentionally the same style used in Phase 1's
notebook 02 (src/data/load_clean.py quality_report) — the same discipline
carried into a new, messier, real-world source.
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_record import WeatherRecord

# Plausibility ranges for India — used for range-check quality flags
PLAUSIBLE_RANGES = {
    "temperature": (-10.0, 55.0),      # Celsius
    "humidity": (0.0, 100.0),          # percent
    "pressure": (870.0, 1085.0),       # hPa
    "rainfall": (0.0, 500.0),          # mm (24hr accumulation, generous upper bound)
    "wind_speed": (0.0, 60.0),         # m/s
}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _kmph_to_ms(kmph: Optional[float]) -> Optional[float]:
    return None if kmph is None else round(kmph / 3.6, 3)


def map_current_wx_to_record(raw: Dict[str, Any]) -> WeatherRecord:
    """Map a single raw current_wx entry (IMD's documented field names) to a
    standardized WeatherRecord. Units are converted here: wind KMPH -> m/s."""
    date_str = raw.get("Date of Observation")
    time_str = raw.get("Time of Observation")
    timestamp = f"{date_str}T{time_str}:00Z" if date_str and time_str else None

    return WeatherRecord(
        source="IMD",
        station_id=raw.get("Station Id"),
        timestamp=timestamp,
        city=raw.get("Station"),
        temperature=_safe_float(raw.get("Temperature")),
        humidity=_safe_float(raw.get("Humidity")),
        pressure=_safe_float(raw.get("M.S.L.P")),
        rainfall=_safe_float(raw.get("Last 24 hrs Rainfall")),
        wind_speed=_kmph_to_ms(_safe_float(raw.get("Wind Speed"))),
        wind_direction=_safe_float(raw.get("Wind Direction")),
        event_type="current_observation",
        description=f"IMD current weather code {raw.get('Weather Code')}",
        raw_payload=raw,
    )


def map_aws_data_to_record(raw: Dict[str, Any]) -> WeatherRecord:
    """Map a single raw aws_data entry (IMD's documented field names) to a
    standardized WeatherRecord."""
    date_str = raw.get("DATE")
    time_str = raw.get("TIME")
    timestamp = f"{date_str}T{time_str}Z" if date_str and time_str else None

    return WeatherRecord(
        source="IMD",
        station_id=raw.get("CALL_SIGN") or raw.get("ID"),
        timestamp=timestamp,
        state=raw.get("STATE"),
        district=raw.get("DISTRICT"),
        city=raw.get("STATION"),
        latitude=_safe_float(raw.get("Latitude")),
        longitude=_safe_float(raw.get("Longitude")),
        temperature=_safe_float(raw.get("CURR_TEMP")),
        humidity=_safe_float(raw.get("RH")),
        pressure=_safe_float(raw.get("MSLP")),
        wind_speed=_kmph_to_ms(_safe_float(raw.get("WIND_SPEED"))),
        wind_direction=_safe_float(raw.get("WIND_DIRECTION")),
        event_type="aws_observation",
        description=f"IMD AWS/ARG station observation, weather code {raw.get('WEATHER_CODE')}",
        raw_payload=raw,
    )


def validate_record(record: WeatherRecord, base_confidence: float = 0.9) -> WeatherRecord:
    """Apply range checks and set verification_status/confidence_score/quality_flags.
    Mutates and returns the same record.

    base_confidence: the confidence assigned when zero flags are raised. Default
    0.9 is unchanged from Phase 2A (a single-source IMD ground observation, no
    cross-check yet). Phase 2B's ERA5 adapter passes a lower base_confidence
    (0.85) since ERA5 is a MODEL reanalysis rather than a direct observation --
    this is a documented, stated assumption, not a measured meteorological fact.
    """
    flags: List[str] = []

    for field_name, (lo, hi) in PLAUSIBLE_RANGES.items():
        value = getattr(record, field_name, None)
        if value is not None and not (lo <= value <= hi):
            flags.append(f"{field_name}_out_of_range")

    if record.timestamp is None:
        flags.append("missing_timestamp")
    if record.latitude is None and record.longitude is None and record.city is None:
        flags.append("no_location_info")

    record.quality_flags = flags

    if flags:
        record.verification_status = "flagged"
        # Confidence drops with each flag raised, floor at 0.1
        record.confidence_score = max(0.1, base_confidence - 0.3 * len(flags))
    else:
        record.verification_status = "validated"
        record.confidence_score = base_confidence

    return record


def process_raw_records(raw_records: List[Dict[str, Any]], endpoint: str) -> List[WeatherRecord]:
    """Full pipeline: map raw IMD JSON entries to WeatherRecords and validate each.
    `endpoint` must be 'current_wx' or 'aws_data'."""
    mapper = {
        "current_wx": map_current_wx_to_record,
        "aws_data": map_aws_data_to_record,
    }.get(endpoint)

    if mapper is None:
        raise ValueError(f"Unknown endpoint '{endpoint}'. Expected 'current_wx' or 'aws_data'.")

    records = []
    for raw in raw_records:
        raw = {k: v for k, v in raw.items() if k != "_fixture_note"}
        rec = mapper(raw)
        rec = validate_record(rec)
        records.append(rec)
    return records
