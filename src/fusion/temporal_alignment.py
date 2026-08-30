"""
Temporal alignment: compares two source timestamps and decides whether they
represent "the same moment" closely enough to be compared/fused.

TEMPORAL MATCHING THRESHOLD -- documented assumption, not a scientific constant:
Default max_time_diff_minutes = 60. ERA5 is hourly; IMD current_wx observations
are typically reported on their own schedule (often near the top of the hour
but not guaranteed). 60 minutes is a reasonable starting tolerance for a
single-hour reanalysis grid; it should be tightened once real, frequent IMD
AWS data (which updates every ~15 minutes) is used in Phase 3+.

Per Part 4's explicit requirement: matching is done on full parsed timestamps,
never on date-only comparison.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import dateutil.parser as dateparser

DEFAULT_MAX_TIME_DIFF_MINUTES = 60.0


@dataclass
class TemporalMatchResult:
    era5_timestamp: Optional[str]
    imd_timestamp: Optional[str]
    time_difference_minutes: Optional[float]
    is_match: bool
    flag: str  # "TEMPORAL_MATCH" | "TEMPORAL_MISMATCH" | "TEMPORAL_UNKNOWN"


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if ts is None:
        return None
    try:
        return dateparser.parse(ts)
    except (ValueError, TypeError):
        return None


def check_temporal_match(era5_timestamp: Optional[str], imd_timestamp: Optional[str],
                          max_time_diff_minutes: float = DEFAULT_MAX_TIME_DIFF_MINUTES) -> TemporalMatchResult:
    """Compare two ISO timestamps. If either is missing/unparseable, the
    match is explicitly TEMPORAL_UNKNOWN -- never assumed just because
    dates happen to match (per Part 4's explicit requirement)."""
    t1, t2 = _parse(era5_timestamp), _parse(imd_timestamp)

    if t1 is None or t2 is None:
        return TemporalMatchResult(era5_timestamp, imd_timestamp, None, False, "TEMPORAL_UNKNOWN")

    diff_minutes = round(abs((t1 - t2).total_seconds()) / 60.0, 2)
    is_match = diff_minutes <= max_time_diff_minutes
    flag = "TEMPORAL_MATCH" if is_match else "TEMPORAL_MISMATCH"

    return TemporalMatchResult(era5_timestamp, imd_timestamp, diff_minutes, is_match, flag)
