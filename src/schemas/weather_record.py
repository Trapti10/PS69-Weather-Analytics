"""
WeatherRecord — the common, source-independent schema for PS69 Phase 2+.

Every ingestion connector (IMD now; ERA5, MOSDAC, weather stations, citizen
reports, social media later) must produce records in this shape. This is the
seam where Phase-3 fusion will eventually operate: fusion logic will consume
lists of WeatherRecord objects from multiple sources for the same
location/time window and reconcile them — it does not need to know anything
about IMD, ERA5, or any other source-specific format.

Design principles:
- Every field a source doesn't provide is left as None, never guessed
- Units are standardized at the connector level before a WeatherRecord is
  built (temperature in Celsius, wind speed in m/s, pressure in hPa,
  rainfall in mm) so downstream code never has to know per-source units
- `raw_payload` retains the original source response for traceability —
  required by the platform's confidence-scoring/fusion methodology
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any


@dataclass
class WeatherRecord:
    # --- Identity & source ---
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""                         # e.g. "IMD", "ERA5", "MOSDAC", "citizen_report"
    station_id: Optional[str] = None         # station/call-sign, when the source is station-based

    # --- When ---
    timestamp: Optional[str] = None          # ISO 8601 UTC — when the observation was made
    ingested_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )                                          # when OUR pipeline pulled this record

    # --- Where ---
    country: Optional[str] = "India"
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # --- Core measurements (standardized units) ---
    temperature: Optional[float] = None       # Celsius
    humidity: Optional[float] = None          # percent
    pressure: Optional[float] = None          # hPa
    rainfall: Optional[float] = None          # mm
    wind_speed: Optional[float] = None        # m/s
    wind_direction: Optional[float] = None    # degrees (0-360) or IMD code, source-dependent

    # --- Event / narrative ---
    event_type: Optional[str] = None          # e.g. "current_observation", "warning", "nowcast"
    description: Optional[str] = None

    # --- Trust & traceability ---
    verification_status: str = "unverified"   # "unverified" | "validated" | "flagged"
    confidence_score: Optional[float] = None  # 0.0-1.0, set by validators/fusion later
    quality_flags: List[str] = field(default_factory=list)
    raw_payload: Optional[Dict[str, Any]] = None  # original source response, for traceability

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
