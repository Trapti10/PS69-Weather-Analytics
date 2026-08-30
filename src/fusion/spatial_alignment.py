"""
Spatial alignment: Haversine distance between two source records, and a
configurable threshold deciding whether they represent "the same place"
closely enough to be compared/fused.

SPATIAL MATCHING THRESHOLD -- documented assumption, not a scientific constant:
Default max_distance_km = 25.0. IMD ground stations are sparse relative to
ERA5's fine reanalysis grid, and a single IMD station is often treated as
representative of a wider district-level area. 25km is a reasonable starting
assumption for a single-station-vs-single-gridpoint comparison; it should be
revisited once real multi-station IMD data (Phase 3+) is available and the
actual station density is known.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

EARTH_RADIUS_KM = 6371.0088
DEFAULT_MAX_DISTANCE_KM = 25.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


@dataclass
class SpatialMatchResult:
    era5_latitude: Optional[float]
    era5_longitude: Optional[float]
    imd_latitude: Optional[float]
    imd_longitude: Optional[float]
    distance_km: Optional[float]
    is_match: bool
    flag: str  # "SPATIAL_MATCH" | "SPATIAL_MISMATCH" | "SPATIAL_UNKNOWN"


def check_spatial_match(era5_lat, era5_lon, imd_lat, imd_lon,
                         max_distance_km: float = DEFAULT_MAX_DISTANCE_KM) -> SpatialMatchResult:
    """Compare two locations. If either source is missing coordinates, the
    match is explicitly SPATIAL_UNKNOWN -- never assumed to match just
    because a city name matches (per Part 5's explicit requirement)."""
    if era5_lat is None or era5_lon is None or imd_lat is None or imd_lon is None:
        return SpatialMatchResult(era5_lat, era5_lon, imd_lat, imd_lon, None, False, "SPATIAL_UNKNOWN")

    distance = round(haversine_km(era5_lat, era5_lon, imd_lat, imd_lon), 3)
    is_match = distance <= max_distance_km
    flag = "SPATIAL_MATCH" if is_match else "SPATIAL_MISMATCH"

    return SpatialMatchResult(era5_lat, era5_lon, imd_lat, imd_lon, distance, is_match, flag)
