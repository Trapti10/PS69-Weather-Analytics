"""
Phase 3C -- Temporal corroboration.

Finds candidate WeatherRecord observations near a WeatherReport's timestamp.
REUSES Phase 2B's src/fusion/temporal_alignment.py::check_temporal_match
for the actual "is this close enough" decision -- this module does not
reimplement that logic, it only adds an efficient way to find candidates
inside a large (17,544-record) sorted evidence series, per the Phase 3C
spec's instruction to "reuse the existing temporal alignment logic where
possible" and to never compare only dates.

TEMPORAL EVIDENCE TOLERANCE -- documented assumption, not a scientific
constant, matching the spirit of Phase 2B's own DEFAULT_MAX_TIME_DIFF_MINUTES.
Default here is wider (90 minutes instead of 60) because a citizen/social
report's stated event time is self-reported and less precise than a second
structured-observation source comparing against another structured source;
this is intentionally documented and independently configurable.
"""
from __future__ import annotations

import sys
import bisect
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.append(str(Path(__file__).resolve().parents[1]))
from fusion.temporal_alignment import check_temporal_match, TemporalMatchResult

DEFAULT_MAX_TIME_DIFF_MINUTES = 90.0


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if ts is None:
        return None
    import dateutil.parser as dateparser
    try:
        return dateparser.parse(ts)
    except (ValueError, TypeError):
        return None


@dataclass
class TemporalEvidenceResult:
    report_timestamp: Optional[str]
    best_match_record_index: Optional[int]   # index into the ORIGINAL (unsorted-input) records list
    time_difference_minutes: Optional[float]
    temporal_match: bool
    flag: str                                 # TEMPORAL_MATCH | TEMPORAL_MISMATCH | TEMPORAL_UNKNOWN
    candidate_record_count: int                # how many records fell within the tolerance window


def build_sorted_time_index(records: List) -> List[Tuple[datetime, int]]:
    """Pre-parses every record's timestamp once and returns a list of
    (parsed_datetime, original_index) sorted by time, skipping records with
    missing/unparseable timestamps (never silently coerced to "now" or
    dropped from the caller's original list -- they simply cannot be a
    temporal-match candidate)."""
    parsed = []
    for i, rec in enumerate(records):
        dt = _parse(getattr(rec, "timestamp", None))
        if dt is not None:
            parsed.append((dt, i))
    parsed.sort(key=lambda pair: pair[0])
    return parsed


def find_temporal_candidates(report_timestamp: Optional[str],
                              records: List,
                              sorted_index: List[Tuple[datetime, int]],
                              max_time_diff_minutes: float = DEFAULT_MAX_TIME_DIFF_MINUTES) -> TemporalEvidenceResult:
    """Finds all records within `max_time_diff_minutes` of the report's
    timestamp using binary search over the pre-sorted index (efficient for
    large evidence series like the real 17,544-record ERA5/Open-Meteo sets),
    then confirms the closest one with the SAME check_temporal_match function
    Phase 2B uses for ERA5<->IMD fusion -- so a report's "temporal match" is
    decided by identical logic to a source-to-source match, not a new rule."""
    report_dt = _parse(report_timestamp)

    if report_dt is None or not sorted_index:
        return TemporalEvidenceResult(report_timestamp, None, None, False, "TEMPORAL_UNKNOWN", 0)

    from datetime import timedelta
    window = timedelta(minutes=max_time_diff_minutes)
    times_only = [t for t, _ in sorted_index]

    lo = bisect.bisect_left(times_only, report_dt - window)
    hi = bisect.bisect_right(times_only, report_dt + window)
    candidates = sorted_index[lo:hi]

    if not candidates:
        return TemporalEvidenceResult(report_timestamp, None, None, False, "TEMPORAL_MISMATCH", 0)

    # Pick the closest candidate, then re-verify with the shared function
    # (never assume the window search alone is the "match" decision).
    best_dt, best_idx = min(candidates, key=lambda pair: abs((pair[0] - report_dt).total_seconds()))
    best_record = records[best_idx]
    match_result: TemporalMatchResult = check_temporal_match(
        report_timestamp, best_record.timestamp, max_time_diff_minutes
    )

    return TemporalEvidenceResult(
        report_timestamp=report_timestamp,
        best_match_record_index=best_idx if match_result.is_match else None,
        time_difference_minutes=match_result.time_difference_minutes,
        temporal_match=match_result.is_match,
        flag=match_result.flag,
        candidate_record_count=len(candidates),
    )
