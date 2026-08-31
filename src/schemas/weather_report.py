"""
WeatherReport — the common schema for Phase 3A's heterogeneous, internet-
sourced weather REPORTS (social media, citizen reports, public datasets,
websites, APIs). Deliberately a SEPARATE dataclass from
src/schemas/weather_record.py: WeatherRecord represents structured
meteorological OBSERVATIONS (ERA5, IMD, Open-Meteo -- numeric sensor/model
values with known units); WeatherReport represents unstructured/semi-
structured human or third-party REPORTS about weather EVENTS (free text,
photos, social posts, citizen submissions) that carry a fundamentally
different trust model (unverified by default, deduplication-prone,
text-based). Merging them into one schema would blur that distinction and
force every meteorological consumer to handle report-only fields (text,
duplicate_hash, is_suspicious) that don't apply to it.

Design principles (same discipline as WeatherRecord):
- Every field a source doesn't provide is left as None, never guessed
- `raw_payload` retains the original source response for traceability
- Fixture/demo data is never silently presented as real -- see
  src/adapters/social_report_adapter.py and citizen_report_adapter.py,
  which preserve an explicit synthetic-data marker inside raw_payload
  rather than stripping it
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# --- Controlled vocabularies (documented, not scientifically fixed) ---

SOURCE_TYPES = {
    "SOCIAL_MEDIA",
    "CITIZEN_REPORT",
    "PUBLIC_DATASET",
    "WEBSITE",
    "API",
}

EVENT_TYPES = {
    "RAINFALL",
    "THUNDERSTORM",
    "FLOODING",
    "HEATWAVE",
    "FOG",
    "DUST_STORM",
    "STRONG_WIND",
    "OTHER",
}

VERIFICATION_STATUSES = {
    "UNVERIFIED",
    "VERIFIED",
    "REJECTED",
    "SUSPICIOUS",
}

# Baseline source-reliability scores -- a STATED, CONFIGURABLE ASSUMPTION,
# not a scientifically validated trust metric. Documented here so it can be
# revisited once real-world precision/recall against verified events exists.
# Callers may override per-report via the `source_reliability` field.
DEFAULT_SOURCE_RELIABILITY = {
    "API": 0.85,               # e.g. an official government/agency API
    "PUBLIC_DATASET": 0.75,    # curated, but not real-time verified
    "WEBSITE": 0.5,            # scraped/aggregated, provenance varies
    "CITIZEN_REPORT": 0.4,     # direct but unverified individual submission
    "SOCIAL_MEDIA": 0.3,       # highest volume, lowest baseline trust
    "UNKNOWN": 0.2,
}


@dataclass
class WeatherReport:
    # --- Identity & source ---
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_type: str = "UNKNOWN"       # one of SOURCE_TYPES (validated, not enforced at construction)
    source_name: Optional[str] = None  # e.g. "X-like-demo-feed", "CitizenAppDemo"
    source_url: Optional[str] = None
    author_id_or_hash: Optional[str] = None  # HASHED identifier -- never a raw name/handle

    # --- When ---
    timestamp: Optional[str] = None    # ISO 8601 UTC -- when the reported event occurred/was posted
    ingestion_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )                                    # when OUR pipeline ingested this report

    # --- Where ---
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # --- Content ---
    text: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    event_type: Optional[str] = None       # normalized, one of EVENT_TYPES
    raw_event_type: Optional[str] = None   # original label/category/hashtag before normalization

    # --- Trust & traceability ---
    verification_status: str = "UNVERIFIED"   # one of VERIFICATION_STATUSES
    source_reliability: Optional[float] = None  # 0.0-1.0 baseline, see DEFAULT_SOURCE_RELIABILITY
    is_suspicious: bool = False
    quality_flags: list = field(default_factory=list)

    # --- Deduplication (Phase 3A: deterministic baseline only) ---
    is_duplicate: bool = False
    duplicate_hash: Optional[str] = None
    duplicate_group_id: Optional[str] = None

    # --- Extensibility / traceability ---
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
