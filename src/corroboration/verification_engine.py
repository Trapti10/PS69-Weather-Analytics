"""
Phase 3C -- Verification engine.

Turns a report_correlator.correlate_report() result into an explainable
verification verdict. This is the ONLY module in Phase 3C that assigns a
verification_status or a numeric evidence_support_score -- every other
module in this package only gathers/aligns raw evidence.

VERIFICATION STATUSES (per the Phase 3C spec, Part 7) -- deliberately four
distinct outcomes, never collapsed into a binary VERIFIED/FAKE:
    SUPPORTED             -- available compatible weather evidence is
                             consistent with the report's claimed event.
    CONFLICTING           -- available compatible weather evidence
                             contradicts the report's claimed event.
    UNVERIFIED            -- evidence exists but is inconclusive (ambiguous
                             values, or sources disagree with each other).
    INSUFFICIENT_EVIDENCE -- no usable evidence at all: missing timestamp,
                             missing location, no temporally/spatially
                             matched record in any source, the event
                             category has no evidence mapping, or every
                             required variable is unavailable in every
                             matched record.

*** SCIENTIFIC HONESTY, non-negotiable (Phase 3C spec Part 15) ***
SUPPORTED must never be read or reported as "this report is true" -- only as
"SUPPORTED BY AVAILABLE WEATHER EVIDENCE". Likewise CONFLICTING must be read
as "CONFLICTING WITH AVAILABLE WEATHER EVIDENCE", not "this report is fake".
ERA5 and Open-Meteo are themselves model/reanalysis products, not ground
truth (see their adapters' docstrings) -- a SUPPORTED verdict is therefore
at most cross-model/observational consistency, never proof.

EVIDENCE_SUPPORT_SCORE -- transparent, deterministic, documented (Phase 3C
spec Part 9). Named "evidence_support_score", explicitly NOT
"truth_probability" -- it is a simple mean of per-source numeric verdict
codes (SUPPORTING=1.0, AMBIGUOUS=0.5, CONFLICTING=0.0) over sources that
actually had a usable, matched value. If no source had a usable value,
the score is None -- never invented.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

# Per-variable evidence thresholds -- documented, stated assumptions, same
# discipline as fusion/source_comparison.py's PERCENT_THRESHOLDS. These are
# NOT scientifically calibrated against verified ground-truth events; they
# are a reasonable, explainable starting point for a hackathon prototype,
# explicitly flagged here so a future phase can replace them with
# calibrated values once labeled real-world outcomes exist.
VARIABLE_THRESHOLDS = {
    "rainfall": {
        "support_min": 0.5,   # mm -- any measurable rainfall counts as consistent with a rain-related claim
        "conflict_max": 0.1,  # mm -- effectively dry across the matched window
        "unit": "mm",
    },
    "temperature": {
        "support_min": 40.0,  # deg C -- commonly cited heatwave-range temperature in much of India
        "conflict_max": 35.0, # deg C -- clearly below heatwave range
        "unit": "\u00b0C",
    },
    "wind_speed": {
        "support_min": 10.8,  # m/s -- ~39 km/h, Beaufort 6 "strong breeze"
        "conflict_max": 5.0,  # m/s -- ~18 km/h, clearly not strong wind
        "unit": "m/s",
    },
    "wind_gust": {
        "support_min": 15.0,
        "conflict_max": 7.0,
        "unit": "m/s",
    },
    "humidity": {
        "support_min": 90.0,  # percent -- necessary-but-not-sufficient proxy for fog
        "conflict_max": 60.0,
        "unit": "%",
        "weak_proxy": True,
    },
}

VERDICT_SCORE = {
    "SUPPORTING_EVIDENCE": 1.0,
    "AMBIGUOUS_EVIDENCE": 0.5,
    "CONFLICTING_EVIDENCE": 0.0,
}


@dataclass
class SourceVerdict:
    source_name: str
    data_label: str
    matched: bool
    unavailable_reason: Optional[str]
    variable_used: Optional[str]
    value: Optional[float]
    verdict: str   # SUPPORTING_EVIDENCE | CONFLICTING_EVIDENCE | AMBIGUOUS_EVIDENCE | VARIABLE_UNAVAILABLE | SOURCE_UNAVAILABLE


def evaluate_variable_value(variable: str, value: Optional[float]) -> str:
    """Applies the documented threshold rule for one variable's value.
    Returns SUPPORTING_EVIDENCE / CONFLICTING_EVIDENCE / AMBIGUOUS_EVIDENCE,
    or VARIABLE_UNAVAILABLE if there is no threshold rule or no value."""
    if value is None:
        return "VARIABLE_UNAVAILABLE"
    thresholds = VARIABLE_THRESHOLDS.get(variable)
    if thresholds is None:
        return "VARIABLE_UNAVAILABLE"
    if value >= thresholds["support_min"]:
        return "SUPPORTING_EVIDENCE"
    if value <= thresholds["conflict_max"]:
        return "CONFLICTING_EVIDENCE"
    return "AMBIGUOUS_EVIDENCE"


def _primary_variable(requirement) -> Optional[str]:
    """The single variable this event category's verdict is decided on:
    the first required variable, or -- for categories like FOG that have
    no required variable at all -- the first supporting variable, capped
    as weak evidence by VARIABLE_THRESHOLDS' weak_proxy flag."""
    if requirement.required:
        return requirement.required[0]
    if requirement.supporting:
        return requirement.supporting[0]
    return None


def build_source_verdicts(correlation_sources: Dict[str, Any], primary_variable: Optional[str]) -> List[SourceVerdict]:
    verdicts = []
    for name, corr in correlation_sources.items():
        if not corr.matched:
            verdicts.append(SourceVerdict(
                source_name=name, data_label=corr.data_label, matched=False,
                unavailable_reason=corr.unavailable_reason,
                variable_used=primary_variable, value=None, verdict="SOURCE_UNAVAILABLE",
            ))
            continue
        value = corr.values.get(primary_variable) if primary_variable else None
        verdict = evaluate_variable_value(primary_variable, value) if primary_variable else "VARIABLE_UNAVAILABLE"
        verdicts.append(SourceVerdict(
            source_name=name, data_label=corr.data_label, matched=True,
            unavailable_reason=None, variable_used=primary_variable, value=value, verdict=verdict,
        ))
    return verdicts


def aggregate_verdicts(verdicts: List[SourceVerdict], weak_proxy: bool = False):
    usable = [v for v in verdicts if v.verdict in VERDICT_SCORE]

    if not usable:
        return "INSUFFICIENT_EVIDENCE", None, [
            "No configured evidence source had a temporally/spatially matched "
            "record with the required variable available."
        ]

    has_support = any(v.verdict == "SUPPORTING_EVIDENCE" for v in usable)
    has_conflict = any(v.verdict == "CONFLICTING_EVIDENCE" for v in usable)
    score = round(sum(VERDICT_SCORE[v.verdict] for v in usable) / len(usable), 4)

    reasons = []
    for v in usable:
        reasons.append(
            f"{v.source_name} ({v.data_label}): {v.variable_used}={v.value} -> {v.verdict}"
        )

    if has_support and has_conflict:
        status = "UNVERIFIED"
        reasons.append(
            "Evidence sources disagree with one another (both supporting and "
            "conflicting signals present) -- individual source evidence is "
            "retained rather than blindly averaged into a single verdict."
        )
    elif has_support and not has_conflict:
        status = "SUPPORTED"
        reasons.append("SUPPORTED BY AVAILABLE WEATHER EVIDENCE, not proof the report is true.")
    elif has_conflict and not has_support:
        status = "CONFLICTING"
        reasons.append("CONFLICTING WITH AVAILABLE WEATHER EVIDENCE, not proof the report is false.")
    else:
        status = "UNVERIFIED"
        reasons.append("Evidence is inconclusive: all matched sources fall in an ambiguous range.")

    if weak_proxy:
        reasons.append(
            "This event category's evidence relies on a weak, indirect proxy "
            "variable (no directly diagnostic variable exists in this "
            "project's schema) -- treat this verdict with extra caution."
        )

    return status, score, reasons


def verify_report(report, correlation: Dict[str, Any]) -> Dict[str, Any]:
    """Builds the full explainable Phase 3C verification result for one
    WeatherReport, preserving (never overwriting) its Phase 3B fields."""
    requirement = correlation.get("requirement")
    sources = correlation.get("sources", {})

    base = {
        "report_id": report.report_id,
        "event_category": report.event_type,
        "predicted_event_category": report.predicted_event_category,   # Phase 3B, preserved
        "event_classification_confidence": report.event_classification_confidence,  # Phase 3B, preserved
        "risk_label": report.risk_label,                                # Phase 3B, preserved
        "risk_score": report.risk_score,                                # Phase 3B, preserved
        "report_timestamp": report.timestamp,
        "latitude": report.latitude,
        "longitude": report.longitude,
    }

    if report.timestamp is None:
        return {**base, "verification_status": "INSUFFICIENT_EVIDENCE", "evidence_sources": [],
                "source_evidence": {}, "temporal_alignment": {}, "spatial_alignment": {},
                "evidence_support_score": None,
                "verification_reasons": ["Report has no timestamp -- cannot be temporally corroborated."],
                "evidence_mapping_notes": None}

    if report.latitude is None or report.longitude is None:
        return {**base, "verification_status": "INSUFFICIENT_EVIDENCE", "evidence_sources": [],
                "source_evidence": {}, "temporal_alignment": {}, "spatial_alignment": {},
                "evidence_support_score": None,
                "verification_reasons": ["Report has no location -- cannot be spatially corroborated."],
                "evidence_mapping_notes": None}

    if requirement is None:
        return {**base, "verification_status": "INSUFFICIENT_EVIDENCE", "evidence_sources": [],
                "source_evidence": {}, "temporal_alignment": {}, "spatial_alignment": {},
                "evidence_support_score": None,
                "verification_reasons": [
                    f"No evidence mapping exists for event category '{report.event_type}'."
                ],
                "evidence_mapping_notes": None}

    primary_variable = _primary_variable(requirement)
    weak_proxy = bool(VARIABLE_THRESHOLDS.get(primary_variable, {}).get("weak_proxy")) if primary_variable else False

    if primary_variable is None:
        return {**base, "verification_status": "INSUFFICIENT_EVIDENCE", "evidence_sources": [],
                "source_evidence": {}, "temporal_alignment": {}, "spatial_alignment": {},
                "evidence_support_score": None,
                "verification_reasons": [
                    f"Event category '{report.event_type}' has no required or supporting variable defined."
                ],
                "evidence_mapping_notes": requirement.notes}

    verdicts = build_source_verdicts(sources, primary_variable)
    status, score, reasons = aggregate_verdicts(verdicts, weak_proxy=weak_proxy)

    source_evidence = {}
    temporal_alignment = {}
    spatial_alignment = {}
    for name, corr in sources.items():
        source_evidence[name] = {
            "data_label": corr.data_label,
            "matched": corr.matched,
            "unavailable_reason": corr.unavailable_reason,
            "matched_record_timestamp": corr.matched_record_timestamp,
            "values": corr.values,
        }
        temporal_alignment[name] = corr.temporal_alignment
        spatial_alignment[name] = corr.spatial_alignment

    matched_source_names = [name for name, corr in sources.items() if corr.matched]

    return {
        **base,
        "verification_status": status,
        "evidence_sources": matched_source_names,
        "source_evidence": source_evidence,
        "temporal_alignment": temporal_alignment,
        "spatial_alignment": spatial_alignment,
        "evidence_support_score": score,
        "verification_reasons": reasons,
        "evidence_mapping_notes": requirement.notes,
    }
