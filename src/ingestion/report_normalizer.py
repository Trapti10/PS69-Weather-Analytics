"""
Normalization for WeatherReport objects (Phase 3A). Runs AFTER validation
(validation checks structural well-formedness of the raw values; this step
standardizes the well-formed ones into a consistent shape for storage,
comparison, and deduplication).

Normalization here is deliberately simple and RULE-BASED (timestamp
reformatting, text whitespace cleanup, title-casing city/state). It does
NOT attempt semantic understanding -- that is explicitly deferred to
Phase 3B (per the project's stated roadmap).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional
import dateutil.parser as dateparser

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_report import WeatherReport, DEFAULT_SOURCE_RELIABILITY


def normalize_timestamp(ts: Optional[str]) -> Optional[str]:
    """Best-effort reformat to a consistent ISO-8601 'Z' UTC string.
    Returns the ORIGINAL string unchanged if it can't be parsed (this
    function never fabricates a timestamp; validate_report already flagged
    unparseable timestamps as invalid/REJECTED upstream)."""
    if not ts:
        return ts
    try:
        parsed = dateparser.parse(ts)
    except (ValueError, TypeError, OverflowError):
        return ts
    if parsed is None:
        return ts
    if parsed.tzinfo is None:
        return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_text(text: Optional[str]) -> Optional[str]:
    """Collapse whitespace and strip -- does not alter meaning or casing."""
    if text is None:
        return None
    return re.sub(r"\s+", " ", text).strip()


def normalized_text_for_dedup(text: Optional[str]) -> str:
    """A more aggressive normalization used ONLY for duplicate-hash
    computation (report_dedup.py) -- lowercased, punctuation stripped,
    whitespace collapsed. Kept separate from normalize_text() above so the
    human-readable `text` field is never mangled for display purposes."""
    if not text:
        return ""
    lowered = text.lower()
    no_punct = re.sub(r"[^\w\s]", "", lowered)
    return re.sub(r"\s+", " ", no_punct).strip()


def normalize_place(name: Optional[str]) -> Optional[str]:
    if not name:
        return name
    return name.strip().title()


def normalize_report(report: WeatherReport) -> WeatherReport:
    """Standardize fields on an already-validated report. Mutates and
    returns the same object. Does NOT change verification_status or
    quality_flags -- those belong to validation."""
    report.timestamp = normalize_timestamp(report.timestamp)
    report.text = normalize_text(report.text)
    report.city = normalize_place(report.city)
    report.state = normalize_place(report.state)

    if report.source_reliability is None:
        report.source_reliability = DEFAULT_SOURCE_RELIABILITY.get(
            report.source_type, DEFAULT_SOURCE_RELIABILITY["UNKNOWN"]
        )

    return report


def normalize_reports(reports: List[WeatherReport]) -> List[WeatherReport]:
    return [normalize_report(r) for r in reports]
