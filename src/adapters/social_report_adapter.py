"""
Social-media report adapter -- Phase 3A's SOCIAL_MEDIA source connector.

*** HONESTY NOTE (read before using) ***
This adapter does NOT have live access to Twitter/X, Instagram, Facebook,
or any real social platform. No such API credentials or integration exist
in this project. It reads from a clearly-labeled SYNTHETIC/DEMO fixture
(data/phase3/fixtures/social_weather_reports.json) so the rest of the
pipeline (validation -> normalization -> dedup -> storage) can be built and
demonstrated now. The architecture is source-agnostic by design (see
`social_fixture_to_reports` vs. a hypothetical future `social_api_to_reports`)
so a real platform integration can be plugged in later without touching
downstream validation/normalization/dedup code.

Every fixture record's `_synthetic_note` is PRESERVED inside `raw_payload`
(not stripped, unlike Phase 2A's IMD fixture convention) so any downstream
consumer of a WeatherReport can always see, from the record itself, that it
originated from synthetic/demo data -- never silently presented as real.

PRIVACY NOTE: `author_handle` from the fixture is hashed into
`author_id_or_hash` before being placed on the WeatherReport -- the raw
handle is not carried onto the standardized record (it remains, for
traceability only, inside `raw_payload`, which is clearly marked synthetic
here; a real integration would need a real data-handling policy for this).
"""
from __future__ import annotations

import sys
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_report import WeatherReport

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "phase3" / "fixtures"

# Simple, documented, RULE-BASED keyword -> event_type heuristic. This is
# NOT NLP/ML classification -- it's a transparent substring match, good
# enough to demonstrate the pipeline. Phase 3B is the right place for a
# real text-classification model. Order matters: first match wins.
EVENT_KEYWORDS = [
    ("FLOODING", ["flood", "waterlogging", "water logging"]),
    ("THUNDERSTORM", ["thunderstorm", "lightning", "thunder"]),
    ("DUST_STORM", ["dust storm", "duststorm", "sandstorm"]),
    ("HEATWAVE", ["heatwave", "heat wave", "extreme heat", "scorching"]),
    ("FOG", ["fog", "mist", "visibility"]),
    ("STRONG_WIND", ["strong wind", "gusty wind", "gale", "windstorm"]),
    ("RAINFALL", ["rain", "rainfall", "downpour", "showers"]),
]


def infer_event_type_from_text(text: str) -> str:
    """Heuristic, rule-based inference -- documented limitation, not ML."""
    if not text:
        return "OTHER"
    lowered = text.lower()
    for event_type, keywords in EVENT_KEYWORDS:
        if any(kw in lowered for kw in keywords):
            return event_type
    return "OTHER"


def _hash_author(handle: str) -> str:
    if not handle:
        return None
    return "sha256:" + hashlib.sha256(handle.encode("utf-8")).hexdigest()[:16]


def load_social_fixture(filename: str = "social_weather_reports.json") -> List[Dict[str, Any]]:
    path = FIXTURES_DIR / filename
    with open(path, "r") as f:
        return json.load(f)


def _raw_to_report(raw: Dict[str, Any]) -> WeatherReport:
    text = raw.get("text")
    hashtags = raw.get("hashtags") or []
    raw_event_type = hashtags[0] if hashtags else None
    event_type = infer_event_type_from_text(text)

    return WeatherReport(
        source_type="SOCIAL_MEDIA",
        source_name=raw.get("platform"),
        source_url=None,  # no real permalink -- this is synthetic data
        author_id_or_hash=_hash_author(raw.get("author_handle")),
        timestamp=raw.get("posted_at"),
        text=text,
        city=raw.get("city"),
        state=raw.get("state"),
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        image_url=raw.get("image_url"),
        video_url=raw.get("video_url"),
        event_type=event_type,
        raw_event_type=raw_event_type,
        raw_payload=raw,  # includes _synthetic_note -- preserved, not stripped
    )


def social_fixture_to_reports(filename: str = "social_weather_reports.json") -> List[WeatherReport]:
    """Load the synthetic social-media fixture and convert every entry into
    a standardized (but NOT yet validated/normalized) WeatherReport."""
    raw_records = load_social_fixture(filename)
    return [_raw_to_report(r) for r in raw_records]
