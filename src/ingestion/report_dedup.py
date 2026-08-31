"""
Deterministic deduplication baseline for WeatherReport objects (Phase 3A).

*** DOCUMENTED, STATED LIMITATION ***
This is intentionally a DETERMINISTIC, RULE-BASED baseline, per the Phase
3A instructions -- no ML/semantic similarity yet (that is explicitly
Phase 3B's job). Two reports are grouped as duplicates only if, after
normalization, they share:
    1. the same normalized event_type
    2. a timestamp within the same rounded time bucket
       (default: 30-minute buckets -- a documented assumption, not a
       measured optimum)
    3. a location within the same rounded coordinate bucket
       (default: 2 decimal degrees, ~1.1km at the equator -- a documented
       assumption, not a measured optimum)
    4. IDENTICAL normalized text (lowercased, punctuation stripped,
       whitespace collapsed -- see report_normalizer.normalized_text_for_dedup)

Consequence (demonstrated in the Phase 3A fixtures/tests): two independent
reports describing the SAME real-world event in DIFFERENT WORDING (e.g. one
person writes "waterlogging near MG Road" and another writes "MG Road is
flooded") will NOT be detected as duplicates by this baseline, even though
a human -- or a future semantic-similarity model -- would recognize them as
the same event. This is a real, acknowledged gap, not an oversight, and is
exactly why Phase 3B (semantic/ML similarity) is the recommended next step.

Grouping is done WITHOUT regard to source_type or source_name deliberately:
the goal is to catch repeated/reposted reports of the same event regardless
of which feed they came in on. Within a batch, the FIRST report encountered
for a given hash is treated as the "original" (is_duplicate=False); every
subsequent report sharing that hash is flagged is_duplicate=True. All
reports sharing a hash (including the original) get the same
duplicate_group_id so they can be queried together.
"""
from __future__ import annotations

import hashlib
import sys
import uuid
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timezone
import dateutil.parser as dateparser

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_report import WeatherReport
from ingestion.report_normalizer import normalized_text_for_dedup

DEFAULT_TIME_BUCKET_MINUTES = 30
DEFAULT_LOCATION_DECIMALS = 2  # ~1.1 km at the equator


def _time_bucket(timestamp: str, bucket_minutes: int) -> str:
    if not timestamp:
        return "UNKNOWN_TIME"
    try:
        dt = dateparser.parse(timestamp)
    except (ValueError, TypeError, OverflowError):
        return "UNKNOWN_TIME"
    if dt is None:
        return "UNKNOWN_TIME"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    epoch_minutes = int(dt.timestamp() // 60)
    bucket = epoch_minutes - (epoch_minutes % bucket_minutes)
    return str(bucket)


def _location_bucket(lat, lon, decimals: int) -> str:
    if lat is None or lon is None:
        return "UNKNOWN_LOCATION"
    return f"{round(lat, decimals)},{round(lon, decimals)}"


def compute_duplicate_hash(report: WeatherReport,
                            time_bucket_minutes: int = DEFAULT_TIME_BUCKET_MINUTES,
                            location_decimals: int = DEFAULT_LOCATION_DECIMALS) -> str:
    """Deterministic hash: same inputs always produce the same hash --
    this is the whole point of a 'deterministic' baseline (no randomness,
    no model inference)."""
    event = report.event_type or "UNKNOWN_EVENT"
    tbucket = _time_bucket(report.timestamp, time_bucket_minutes)
    lbucket = _location_bucket(report.latitude, report.longitude, location_decimals)
    ntext = normalized_text_for_dedup(report.text)

    key = f"{event}|{tbucket}|{lbucket}|{ntext}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def detect_duplicates(reports: List[WeatherReport],
                       time_bucket_minutes: int = DEFAULT_TIME_BUCKET_MINUTES,
                       location_decimals: int = DEFAULT_LOCATION_DECIMALS) -> List[WeatherReport]:
    """Mutates and returns the same list of reports, setting duplicate_hash,
    duplicate_group_id, and is_duplicate on each. Order-dependent: whichever
    report appears first in `reports` for a given hash is treated as the
    non-duplicate original."""
    seen: Dict[str, str] = {}  # hash -> group_id

    for report in reports:
        h = compute_duplicate_hash(report, time_bucket_minutes, location_decimals)
        report.duplicate_hash = h

        if h not in seen:
            seen[h] = str(uuid.uuid4())
            report.duplicate_group_id = seen[h]
            report.is_duplicate = False
        else:
            report.duplicate_group_id = seen[h]
            report.is_duplicate = True

    return reports
