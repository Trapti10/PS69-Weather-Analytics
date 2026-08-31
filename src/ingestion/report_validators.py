"""
Validation for WeatherReport objects (Phase 3A). Mirrors the discipline of
src/ingestion/validators.py (Phase 2A) but is intentionally a SEPARATE
module: WeatherReport has different required fields, different failure
modes (free text, no numeric plausibility ranges), and a different
verification-status vocabulary (UNVERIFIED/VERIFIED/REJECTED/SUSPICIOUS
vs. WeatherRecord's unverified/validated/flagged).

CORE RULE: invalid records are FLAGGED and/or REJECTED, never silently
discarded. Every report that goes into `validate_report` comes back out
(same object, mutated), so the caller can still store, count, and inspect
it -- including reports later marked REJECTED.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List
import dateutil.parser as dateparser

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_report import WeatherReport, SOURCE_TYPES, EVENT_TYPES

# Documented assumption, not a hard technical limit -- flags unusually long
# text as a data-quality signal (possible scraping error, spam, or pasted
# content), not an outright rejection.
MAX_TEXT_LENGTH = 2000
MIN_MEANINGFUL_TEXT_LENGTH = 3  # empty/near-empty text is a real signal, not noise


def _parse_timestamp(ts):
    if not ts:
        return None
    try:
        return dateparser.parse(ts)
    except (ValueError, TypeError, OverflowError):
        return None


def validate_report(report: WeatherReport) -> WeatherReport:
    """Apply structural validation and set verification_status/quality_flags.
    Mutates and returns the same report -- never drops it.

    Rejection (verification_status = "REJECTED") is reserved for records
    that are PHYSICALLY IMPOSSIBLE or structurally unusable (bad lat/lon,
    unparseable/missing timestamp, unknown source_type). Everything else
    that looks unusual (empty text + unrecognized category, no location at
    all) is flagged SUSPICIOUS instead, since it may still carry real
    information -- SUSPICIOUS reports are kept in the pipeline for a human
    or a future ML layer (Phase 3B) to review, not thrown away.
    """
    flags: List[str] = []
    reject = False
    suspicious = False

    # --- source_type ---
    if report.source_type not in SOURCE_TYPES:
        flags.append(f"unknown_source_type:{report.source_type}")
        reject = True

    # --- timestamp ---
    parsed_ts = _parse_timestamp(report.timestamp)
    if report.timestamp is None:
        flags.append("missing_timestamp")
        reject = True
    elif parsed_ts is None:
        flags.append("invalid_timestamp_format")
        reject = True

    # --- latitude / longitude ---
    if report.latitude is not None and not (-90.0 <= report.latitude <= 90.0):
        flags.append("invalid_latitude")
        reject = True
    if report.longitude is not None and not (-180.0 <= report.longitude <= 180.0):
        flags.append("invalid_longitude")
        reject = True

    # --- location presence (city/state OR lat/lon must exist in SOME form) ---
    has_named_location = bool(report.city or report.state)
    has_coords = report.latitude is not None and report.longitude is not None
    if not has_named_location and not has_coords:
        flags.append("no_location_info")
        suspicious = True

    # --- event type ---
    if report.event_type not in EVENT_TYPES:
        flags.append(f"invalid_event_type:{report.event_type}")
        suspicious = True
    if report.event_type == "OTHER" and report.raw_event_type is not None:
        flags.append("event_type_normalized_to_other")

    # --- text ---
    text = report.text or ""
    if len(text.strip()) < MIN_MEANINGFUL_TEXT_LENGTH:
        flags.append("empty_or_near_empty_text")
        suspicious = True
    if len(text) > MAX_TEXT_LENGTH:
        flags.append("text_too_long")
        suspicious = True

    # --- combine: empty text AND unrecognized event -> genuinely low-value report ---
    if "empty_or_near_empty_text" in flags and "invalid_event_type" in " ".join(flags):
        suspicious = True

    report.quality_flags = flags

    if reject:
        report.verification_status = "REJECTED"
    elif suspicious:
        report.verification_status = "SUSPICIOUS"
        report.is_suspicious = True
    else:
        report.verification_status = "UNVERIFIED"  # never auto-VERIFIED, per Phase 3A instructions

    return report


def validate_reports(reports: List[WeatherReport]) -> List[WeatherReport]:
    return [validate_report(r) for r in reports]
