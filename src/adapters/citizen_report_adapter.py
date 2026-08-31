"""
Citizen-report adapter -- Phase 3A's CITIZEN_REPORT source connector.

*** HONESTY NOTE (read before using) ***
This adapter does NOT connect to any real citizen-reporting app or backend.
It reads from a clearly-labeled SYNTHETIC/DEMO fixture
(data/phase3/fixtures/citizen_weather_reports.json). See
social_report_adapter.py's module docstring for the same honesty/traceability
principles, which apply identically here (synthetic marker preserved in
raw_payload, submitter identity hashed, source-agnostic architecture so a
real citizen-app API can be plugged in later).
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_report import WeatherReport

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "phase3" / "fixtures"

# Direct category -> event_type mapping (citizen apps typically offer a
# fixed dropdown, unlike free-text social posts, so no keyword heuristic
# is needed here -- just normalization of casing/spelling).
CATEGORY_TO_EVENT_TYPE = {
    "rainfall": "RAINFALL",
    "rain": "RAINFALL",
    "thunderstorm": "THUNDERSTORM",
    "flooding": "FLOODING",
    "flood": "FLOODING",
    "heatwave": "HEATWAVE",
    "heat_wave": "HEATWAVE",
    "fog": "FOG",
    "dust_storm": "DUST_STORM",
    "duststorm": "DUST_STORM",
    "strong_wind": "STRONG_WIND",
    "strong wind": "STRONG_WIND",
}


def normalize_category(raw_category: str) -> str:
    if not raw_category:
        return "OTHER"
    return CATEGORY_TO_EVENT_TYPE.get(raw_category.strip().lower(), "OTHER")


def load_citizen_fixture(filename: str = "citizen_weather_reports.json") -> List[Dict[str, Any]]:
    path = FIXTURES_DIR / filename
    with open(path, "r") as f:
        return json.load(f)


def _raw_to_report(raw: Dict[str, Any]) -> WeatherReport:
    raw_category = raw.get("category")
    return WeatherReport(
        source_type="CITIZEN_REPORT",
        source_name="CitizenReportAppDemo",
        source_url=None,  # no real backend -- this is synthetic data
        author_id_or_hash=raw.get("submitted_by_hash"),  # fixture already provides a hash-shaped id
        timestamp=raw.get("submitted_at"),
        text=raw.get("description"),
        city=raw.get("city"),
        state=raw.get("state"),
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        image_url=raw.get("photo_url"),
        video_url=raw.get("video_url"),
        event_type=normalize_category(raw_category),
        raw_event_type=raw_category,
        raw_payload=raw,  # includes _synthetic_note -- preserved, not stripped
    )


def citizen_fixture_to_reports(filename: str = "citizen_weather_reports.json") -> List[WeatherReport]:
    """Load the synthetic citizen-report fixture and convert every entry
    into a standardized (but NOT yet validated/normalized) WeatherReport."""
    raw_records = load_citizen_fixture(filename)
    return [_raw_to_report(r) for r in raw_records]
