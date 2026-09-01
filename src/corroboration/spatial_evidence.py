"""
Phase 3C -- Spatial corroboration.

Thin wrapper around Phase 2B's src/fusion/spatial_alignment.py::check_spatial_match
(Haversine distance + configurable threshold) -- reused unmodified, per the
Phase 3C spec's instruction to reuse the existing spatial alignment
implementation. This module adds nothing but an explicit
"missing/invalid location" handling path so report_correlator.py never has
to guess a report's location.

SPATIAL EVIDENCE THRESHOLD -- documented assumption. Default is
DEFAULT_MAX_DISTANCE_KM (imported straight from spatial_alignment.py, 25 km)
so citizen/social reports are held to the SAME spatial tolerance already
used for ERA5<->IMD source comparison, rather than inventing a second
threshold with no stated justification.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.append(str(Path(__file__).resolve().parents[1]))
from fusion.spatial_alignment import check_spatial_match, DEFAULT_MAX_DISTANCE_KM, SpatialMatchResult


@dataclass
class SpatialEvidenceResult:
    report_latitude: Optional[float]
    report_longitude: Optional[float]
    record_latitude: Optional[float]
    record_longitude: Optional[float]
    distance_km: Optional[float]
    spatial_match: bool
    flag: str  # SPATIAL_MATCH | SPATIAL_MISMATCH | SPATIAL_UNKNOWN | SPATIAL_INSUFFICIENT (report has no location at all)


def evaluate_spatial_evidence(report_lat: Optional[float], report_lon: Optional[float],
                               record_lat: Optional[float], record_lon: Optional[float],
                               max_distance_km: float = DEFAULT_MAX_DISTANCE_KM) -> SpatialEvidenceResult:
    """Never assumes a match just because a city name matches (per the
    Phase 3C spec's explicit instruction) -- only real lat/lon comparison,
    or an explicit UNKNOWN/INSUFFICIENT status."""
    if report_lat is None or report_lon is None:
        return SpatialEvidenceResult(report_lat, report_lon, record_lat, record_lon,
                                      None, False, "SPATIAL_INSUFFICIENT")

    result: SpatialMatchResult = check_spatial_match(
        report_lat, report_lon, record_lat, record_lon, max_distance_km
    )
    return SpatialEvidenceResult(
        report_latitude=result.era5_latitude,   # generic positional reuse: "era5_*" fields are position 1 (the report here)
        report_longitude=result.era5_longitude,
        record_latitude=result.imd_latitude,    # "imd_*" fields are position 2 (the evidence record here)
        record_longitude=result.imd_longitude,
        distance_km=result.distance_km,
        spatial_match=result.is_match,
        flag=result.flag,
    )
