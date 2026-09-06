"""
Phase 5: Event Correlation and Clustering

Groups related weather reports into WeatherEvent aggregates.

Uses:
- Exact duplicate hash (Phase 3A)
- Temporal overlap (±3 hours)
- Spatial proximity (Haversine distance, 10 km threshold)
- Event type consistency

NO ML-based event fusion - uses simple, deterministic rules reusing Phase 2B/2C logic.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from math import radians, cos, sin, asin, sqrt
import logging

logger = logging.getLogger(__name__)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on earth (in kilometers).
    
    Reuses the Haversine formula from Phase 2B spatial alignment.
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c  # Radius of earth in kilometers
    return km


def temporal_overlap(
    start_time_1: datetime,
    end_time_1: Optional[datetime],
    start_time_2: datetime,
    end_time_2: Optional[datetime],
    window_hours: int = 3
) -> bool:
    """
    Check if two temporal windows overlap (with a configurable expansion window).
    
    Considers windows overlapping if they are within ±window_hours of each other.
    Default 3-hour window matches Phase 3C evidence lookup logic.
    """
    # Expand windows by ±window_hours
    window_delta = timedelta(hours=window_hours)
    
    expanded_start_1 = start_time_1 - window_delta
    expanded_end_1 = (end_time_1 or start_time_1) + window_delta
    
    expanded_start_2 = start_time_2 - window_delta
    expanded_end_2 = (end_time_2 or start_time_2) + window_delta
    
    # Check overlap: start1 <= end2 AND start2 <= end1
    return expanded_start_1 <= expanded_end_2 and expanded_start_2 <= expanded_end_1


def event_type_compatible(type1: str, type2: str) -> bool:
    """
    Check if two event types are compatible for correlation.
    
    For MVP, only exact match is required.
    Future phases can add domain knowledge (e.g., FLOODING ~= HEAVY_RAIN).
    """
    return type1.upper() == type2.upper()


def should_correlate_reports(
    report1: dict,
    report2: dict,
    duplicate_hash_threshold: bool = True,
    spatial_threshold_km: float = 10.0,
    temporal_window_hours: int = 3,
) -> bool:
    """
    Determine if two reports should be correlated into the same event.
    
    Returns True if reports meet ANY of these conditions:
    1. Exact duplicate hash (Phase 3A)
    2. Spatially close AND temporally overlapping AND same event type
    
    Args:
        report1, report2: Report dicts with timestamp, latitude, longitude, event_type
        duplicate_hash_threshold: Use exact hash if available
        spatial_threshold_km: Haversine distance threshold
        temporal_window_hours: Time window for overlap
    
    Returns:
        bool: True if reports should be in the same event
    """
    # Check 1: Exact duplicate hash
    if duplicate_hash_threshold:
        hash1 = report1.get("duplicate_hash")
        hash2 = report2.get("duplicate_hash")
        if hash1 and hash2 and hash1 == hash2:
            logger.debug(f"Correlating reports by duplicate hash: {hash1}")
            return True
    
    # Check 2: Spatial + temporal + event type
    try:
        lat1 = report1.get("latitude")
        lon1 = report1.get("longitude")
        lat2 = report2.get("latitude")
        lon2 = report2.get("longitude")
        
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            logger.debug("Cannot correlate: missing coordinates")
            return False
        
        # Spatial proximity
        distance_km = haversine_distance_km(lat1, lon1, lat2, lon2)
        if distance_km > spatial_threshold_km:
            logger.debug(f"Reports too far apart: {distance_km:.2f} km")
            return False
        
        # Temporal overlap
        time1 = report1.get("timestamp") or report1.get("report_timestamp")
        time2 = report2.get("timestamp") or report2.get("report_timestamp")
        
        if not time1 or not time2:
            logger.debug("Cannot correlate: missing timestamps")
            return False
        
        # Convert to datetime if string
        if isinstance(time1, str):
            time1 = datetime.fromisoformat(time1.replace("Z", "+00:00"))
        if isinstance(time2, str):
            time2 = datetime.fromisoformat(time2.replace("Z", "+00:00"))
        
        if not temporal_overlap(time1, None, time2, None, temporal_window_hours):
            logger.debug(f"Reports not temporally aligned (window: {temporal_window_hours}h)")
            return False
        
        # Event type compatibility
        type1 = report1.get("event_type", "OTHER")
        type2 = report2.get("event_type", "OTHER")
        if not event_type_compatible(type1, type2):
            logger.debug(f"Event types don't match: {type1} vs {type2}")
            return False
        
        logger.debug(
            f"Reports correlate: {distance_km:.2f} km, same event type, temporally aligned"
        )
        return True
    
    except Exception as e:
        logger.error(f"Error correlating reports: {e}")
        return False


def compute_event_centroid(
    reports: List[dict]
) -> Tuple[float, float]:
    """
    Compute the geographic centroid of a group of reports.
    
    Simple average of all latitudes and longitudes.
    """
    if not reports:
        return 0.0, 0.0
    
    lats = [r.get("latitude", 0) for r in reports if r.get("latitude")]
    lons = [r.get("longitude", 0) for r in reports if r.get("longitude")]
    
    if not lats or not lons:
        return 0.0, 0.0
    
    return sum(lats) / len(lats), sum(lons) / len(lons)


def compute_event_time_bounds(
    reports: List[dict]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Compute the temporal bounds (earliest to latest) of a group of reports.
    """
    times = []
    for r in reports:
        t = r.get("timestamp") or r.get("report_timestamp")
        if t:
            if isinstance(t, str):
                t = datetime.fromisoformat(t.replace("Z", "+00:00"))
            times.append(t)
    
    if not times:
        return None, None
    
    return min(times), max(times)


def get_event_severity(reports: List[dict]) -> str:
    """
    Determine event severity based on risk scores of member reports.
    
    Severity mapping (MVP baseline):
    - HIGH risk score (>0.7): EXTREME
    - MEDIUM risk score (0.5-0.7): HIGH
    - LOW risk score (<0.5): MEDIUM
    - Fallback: MEDIUM
    """
    if not reports:
        return "MEDIUM"
    
    risk_scores = [r.get("risk_score", 0.5) for r in reports]
    avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.5
    
    if avg_risk > 0.7:
        return "EXTREME"
    elif avg_risk > 0.5:
        return "HIGH"
    else:
        return "MEDIUM"


def group_reports_by_event(
    new_report: dict,
    existing_reports: List[dict],
    spatial_threshold_km: float = 10.0,
    temporal_window_hours: int = 3,
) -> Tuple[Optional[str], List[dict]]:
    """
    Find which event group (if any) a new report belongs to.
    
    Returns:
        (event_group_id, [correlated_reports]): 
        - event_group_id: group identifier (e.g., duplicate_group_id, or None if new)
        - [correlated_reports]: list of reports that correlate with new_report
    """
    correlated = []
    
    for existing_report in existing_reports:
        if should_correlate_reports(
            new_report,
            existing_report,
            spatial_threshold_km=spatial_threshold_km,
            temporal_window_hours=temporal_window_hours,
        ):
            correlated.append(existing_report)
    
    # Use the duplicate_group_id from the first correlated report, or generate new
    if correlated:
        event_group_id = correlated[0].get("duplicate_group_id") or new_report.get(
            "duplicate_group_id"
        )
        return event_group_id, correlated
    
    # No correlation found - new event
    return None, []


def prepare_event_data(
    new_report: dict,
    correlated_reports: List[dict],
    evidence_status: str,
    evidence_support_score: Optional[float],
    evidence_detail: dict,
) -> dict:
    """
    Prepare the WeatherEvent record data from reports and evidence.
    
    Combines multiple reports into a single event with:
    - Location: geographic centroid of all reports
    - Time: earliest to latest timestamp
    - Members: all report IDs
    - Evidence: system-assigned status and score
    """
    # All reports for this event
    all_reports = correlated_reports + [new_report]
    
    # Location centroid
    centroid_lat, centroid_lon = compute_event_centroid(all_reports)
    
    # Time bounds
    start_time, end_time = compute_event_time_bounds(all_reports)
    
    # Severity
    severity = get_event_severity(all_reports)
    
    # Report IDs
    report_ids = [r.get("report_id") for r in all_reports if r.get("report_id")]
    
    # Unique sources
    sources = set()
    for r in all_reports:
        source_name = r.get("source_name")
        if source_name:
            sources.add(source_name)
    
    return {
        "event_type": new_report.get("event_type", "OTHER"),
        "location": {"latitude": centroid_lat, "longitude": centroid_lon},
        "location_name": new_report.get("city", "Unknown"),
        "start_time": start_time,
        "end_time": end_time,
        "severity": severity,
        "evidence_status": evidence_status,
        "evidence_support_score": evidence_support_score,
        "evidence_detail": evidence_detail,
        "final_verification_status": "NEEDS_REVIEW",
        "member_report_ids": report_ids,
        "report_count": len(all_reports),
        "unique_sources": len(sources),
    }
