"""
Phase 4A -- Unified Weather Intelligence layer.

Purpose (per the Phase 4A spec): create a clean, unified representation
that brings together the outputs of the existing pipeline --

    ERA5 --\
    IMD ----\
             --> Multi-source Fusion (Phase 2B/2C, reused unmodified)
    Open-Meteo/
                 \
                  --> Weather Intelligence (THIS MODULE)
    Social/Citizen Reports
                 /
                /
    Corroboration (Phase 3C, reused unmodified)

This module does NOT re-implement fusion, corroboration, temporal
alignment, or spatial alignment -- it imports and reuses the existing,
already-tested Phase 2B (`fusion.temporal_alignment`,
`fusion.spatial_alignment`, `fusion.fusion_engine`) and Phase 3C
(`corroboration.verification_engine`) functions exactly as they are.
Phase 4A's own job is narrow: take one already-fused (or single-source)
weather data point plus zero or more already-verified report results, and
assemble them into one explainable `WeatherIntelligence` object.

Phase 4A is explicitly NOT:
- the advanced ML layer
- anomaly detection (the `anomaly` field exists so a LATER phase has a
  place to put results -- Phase 4A never populates it)
- a forecasting engine (the `forecast` field exists for the same reason)
- an alerting system (the `alert` field exists for the same reason)

*** CONFIDENCE, non-negotiable (per the Phase 4A spec) ***
`overall_confidence` is a transparent, documented combination of two
already-existing, separately-named metrics -- `source_agreement_confidence`
(Phase 2B/2C's own confidence score, unmodified) and `evidence_support_score`
(Phase 3C's own score, unmodified, aggregated across the reports selected for
this record). It is NEVER a probability of truth, and it is None whenever
neither input metric is available -- never fabricated. See
`compute_overall_confidence()`'s docstring for the exact rule.
"""
from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fusion.temporal_alignment import check_temporal_match, DEFAULT_MAX_TIME_DIFF_MINUTES
from fusion.spatial_alignment import check_spatial_match, DEFAULT_MAX_DISTANCE_KM

# The WeatherRecord variable names Phase 4A carries forward -- deliberately
# the same set WeatherRecord already defines (src/schemas/weather_record.py),
# so Phase 4A never invents a new unit or a new variable this project's
# schema doesn't already have.
WEATHER_VARIABLE_KEYS = [
    "temperature", "humidity", "pressure", "rainfall", "wind_speed", "wind_direction",
]

# Rollup states -- intentionally the exact same four states Phase 3C's
# verification_engine already defines, applied here to a SET of reports
# rather than a single one. Never collapsed into a binary true/false.
CORROBORATION_STATES = {"SUPPORTED", "CONFLICTING", "UNVERIFIED", "INSUFFICIENT_EVIDENCE"}


@dataclass
class WeatherIntelligence:
    # --- Identity ---
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # --- When / where (per spec items 1-4) ---
    timestamp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    country: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None

    # --- Weather variables (per spec item 5) ---
    # One value per WEATHER_VARIABLE_KEYS entry, None where unavailable --
    # never guessed. Populated from a fusion result's fused values when a
    # multi-source fusion result is supplied, or straight from a single
    # WeatherRecord's fields when only one source is available.
    weather_variables: Dict[str, Optional[float]] = field(default_factory=dict)

    # --- Provenance (per spec item 6) ---
    contributing_sources: List[str] = field(default_factory=list)  # e.g. ["ERA5", "Open-Meteo"]

    # --- Source agreement (per spec item 7) ---
    # Copied, not recomputed, from Phase 2B/2C's fuse_pair() output. None
    # for a single-source record -- there is nothing to agree/disagree on.
    source_agreement_confidence: Optional[float] = None       # fuse_pair()'s "confidence_score"
    source_agreement_match_status: Optional[str] = None       # "MATCHED" | "NOT_MATCHED" | None
    source_agreement_details: Dict[str, Any] = field(default_factory=dict)  # per-variable agreement flags
    source_agreement_marginal: Optional[bool] = None

    # --- Report / corroboration evidence (per spec items 8-9) ---
    # Each entry is a (trimmed, not re-derived) copy of one Phase 3C
    # verify_report() result already computed elsewhere -- Phase 4A never
    # re-runs temporal/spatial matching against evidence sources itself.
    report_evidence: List[Dict[str, Any]] = field(default_factory=list)
    corroboration_status: Optional[str] = None      # one of CORROBORATION_STATES, or None if never assessed
    corroboration_reasons: List[str] = field(default_factory=list)

    # --- Confidence (per spec item 10) ---
    # Three DISTINCT, separately-named numbers -- never merged into one
    # unexplained "confidence" and never described as a probability of truth.
    evidence_support_score: Optional[float] = None    # mean of report_evidence's own scores, or None
    overall_confidence: Optional[float] = None         # see compute_overall_confidence()
    confidence_method: Optional[str] = None            # exact, human-readable description of the combination used

    # --- Reserved for LATER phases, per explicit instruction NOT to implement here ---
    forecast: Optional[Dict[str, Any]] = None   # Phase 4A allows the field to exist; never populated here
    anomaly: Optional[Dict[str, Any]] = None    # Phase 4A allows the field to exist; never populated here
    alert: Optional[Dict[str, Any]] = None      # Phase 4A allows the field to exist; never populated here

    # --- Extensibility / traceability ---
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "WeatherIntelligence":
        known_fields = {f for f in WeatherIntelligence.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return WeatherIntelligence(**filtered)


# ---------------------------------------------------------------------------
# Weather-variable extraction
# ---------------------------------------------------------------------------

def _weather_variables_from_fusion(fusion_result: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Reads the already-computed fused values out of a fuse_pair() result.
    Per fusion_engine.py's own documented rule, a variable's fused value is
    None whenever that variable's sources disagreed (SOURCE_DISAGREEMENT) --
    Phase 4A preserves that None exactly, never averaging around it."""
    fusion = fusion_result.get("fusion", {}) or {}
    return {k: fusion.get(k) for k in WEATHER_VARIABLE_KEYS}


def _weather_variables_from_record(record: Any) -> Dict[str, Optional[float]]:
    """Reads variables directly from a single WeatherRecord (object or dict) --
    used when only one contributing source is available, so there is no
    fusion/agreement step to run."""
    if isinstance(record, dict):
        return {k: record.get(k) for k in WEATHER_VARIABLE_KEYS}
    return {k: getattr(record, k, None) for k in WEATHER_VARIABLE_KEYS}


# ---------------------------------------------------------------------------
# Report-evidence selection (reuses Phase 2B's generic temporal/spatial
# alignment functions unmodified -- see module docstring)
# ---------------------------------------------------------------------------

def select_report_evidence(
    timestamp: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    verification_results: List[Dict[str, Any]],
    max_time_diff_minutes: float = DEFAULT_MAX_TIME_DIFF_MINUTES,
    max_distance_km: float = DEFAULT_MAX_DISTANCE_KM,
) -> List[Dict[str, Any]]:
    """Selects which pre-computed Phase 3C verify_report() results belong to
    this weather-intelligence record, by reusing (not reimplementing)
    check_temporal_match/check_spatial_match on the report's own
    report_timestamp/latitude/longitude fields (already present in every
    verify_report() output). Returns a trimmed summary of each match --
    never the full nested source_evidence blob, to keep WeatherIntelligence
    a genuinely unified/compact representation rather than a re-export of
    Phase 3C's raw output."""
    if timestamp is None or latitude is None or longitude is None:
        return []

    selected = []
    for result in verification_results:
        r_ts = result.get("report_timestamp")
        r_lat = result.get("latitude")
        r_lon = result.get("longitude")
        if r_ts is None or r_lat is None or r_lon is None:
            continue

        temporal = check_temporal_match(timestamp, r_ts, max_time_diff_minutes)
        if not temporal.is_match:
            continue
        spatial = check_spatial_match(latitude, longitude, r_lat, r_lon, max_distance_km)
        if not spatial.is_match:
            continue

        selected.append({
            "report_id": result.get("report_id"),
            "event_category": result.get("event_category"),
            "verification_status": result.get("verification_status"),
            "evidence_support_score": result.get("evidence_support_score"),
            "risk_label": result.get("risk_label"),
            "risk_score": result.get("risk_score"),
            "report_timestamp": r_ts,
            "time_difference_minutes": temporal.time_difference_minutes,
            "distance_km": spatial.distance_km,
        })
    return selected


# ---------------------------------------------------------------------------
# Corroboration rollup (per spec's "CORROBORATION ROLLUP" section)
# ---------------------------------------------------------------------------

def rollup_corroboration_status(report_evidence: List[Dict[str, Any]]) -> (str, List[str]):
    """Rolls up zero or more Phase 3C verification_status values into ONE
    of the same four states, per explicit instruction never to average
    conflicting evidence into a single "truth" value.

    Rule, stated plainly:
    - No report evidence at all -> INSUFFICIENT_EVIDENCE (nothing to assess).
    - Every selected report is itself INSUFFICIENT_EVIDENCE -> INSUFFICIENT_EVIDENCE.
    - Otherwise, among the non-INSUFFICIENT_EVIDENCE reports:
        - both SUPPORTED and CONFLICTING present -> CONFLICTING (the
          disagreement itself is the honest signal; this is a deliberate
          choice to surface conflict rather than hide it behind UNVERIFIED).
        - only CONFLICTING present -> CONFLICTING.
        - SUPPORTED present with no CONFLICTING and no UNVERIFIED -> SUPPORTED.
        - anything else (e.g. UNVERIFIED present, or a SUPPORTED+UNVERIFIED
          mix with no CONFLICTING) -> UNVERIFIED.
    """
    if not report_evidence:
        return "INSUFFICIENT_EVIDENCE", ["No corroborating report evidence is available for this time/location."]

    statuses = [r.get("verification_status") for r in report_evidence if r.get("verification_status")]
    non_insufficient = [s for s in statuses if s != "INSUFFICIENT_EVIDENCE"]

    if not non_insufficient:
        return "INSUFFICIENT_EVIDENCE", [
            f"{len(statuses)} report(s) matched this time/location, but all were themselves "
            "INSUFFICIENT_EVIDENCE in Phase 3C."
        ]

    has_supported = "SUPPORTED" in non_insufficient
    has_conflicting = "CONFLICTING" in non_insufficient
    has_unverified = "UNVERIFIED" in non_insufficient

    if has_supported and has_conflicting:
        return "CONFLICTING", [
            "Reports matched to this record disagree with one another (both SUPPORTED and "
            "CONFLICTING verdicts present) -- preserved as CONFLICTING rather than averaged away."
        ]
    if has_conflicting:
        return "CONFLICTING", ["At least one matched report's evidence conflicted with its claimed event."]
    if has_supported and not has_unverified:
        return "SUPPORTED", ["All matched reports with usable evidence were SUPPORTED."]
    return "UNVERIFIED", ["Matched report evidence exists but is inconclusive (UNVERIFIED)."]


# ---------------------------------------------------------------------------
# Confidence (per spec's "CONFIDENCE" section)
# ---------------------------------------------------------------------------

def compute_evidence_support_score(report_evidence: List[Dict[str, Any]]) -> Optional[float]:
    """Transparent mean of the selected reports' own Phase 3C
    evidence_support_score values -- same discipline as Phase 3C's own
    corroboration_storage.py summary. None if no matched report carries a
    usable (non-None) score -- never invented."""
    scores = [r["evidence_support_score"] for r in report_evidence if r.get("evidence_support_score") is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 4)


def compute_overall_confidence(
    source_agreement_confidence: Optional[float],
    evidence_support_score: Optional[float],
) -> (Optional[float], str):
    """Combines two ALREADY-COMPUTED, separately-named metrics:
      - source_agreement_confidence: how well the weather-observation
        sources (ERA5/IMD/Open-Meteo) agreed with each other (Phase 2B/2C).
      - evidence_support_score: how well matched report evidence aligned
        with its claimed event (Phase 3C).

    Rule, stated exactly (documented per the spec's explicit requirement):
    overall_confidence = the mean of whichever of the two inputs are not
    None. If BOTH are None, overall_confidence is None -- never fabricated.
    If only one is available, overall_confidence equals that one value
    exactly (a mean of one number), not silently treated as "full
    confidence" or padded with an assumed value for the missing one.

    overall_confidence is explicitly NOT a probability that the weather
    event described is true -- it is a transparent average of two
    already-explainable component scores, and unavailable evidence is
    NEVER treated as agreement.
    """
    parts = [v for v in (source_agreement_confidence, evidence_support_score) if v is not None]
    if not parts:
        return None, (
            "No source_agreement_confidence (no multi-source fusion available) and no "
            "evidence_support_score (no usable report evidence available) -- overall_confidence "
            "is None, not fabricated."
        )
    value = round(sum(parts) / len(parts), 4)
    if len(parts) == 2:
        method = (
            "overall_confidence = mean(source_agreement_confidence, evidence_support_score) "
            f"= mean({source_agreement_confidence}, {evidence_support_score}) = {value}. "
            "This is a transparent average of two independently-documented component scores, "
            "NOT a probability that the underlying weather event is true."
        )
    elif source_agreement_confidence is not None:
        method = (
            f"overall_confidence = source_agreement_confidence = {value} "
            "(no evidence_support_score was available to combine with it; the missing input "
            "is NOT treated as agreement or disagreement)."
        )
    else:
        method = (
            f"overall_confidence = evidence_support_score = {value} "
            "(no source_agreement_confidence was available to combine with it; the missing input "
            "is NOT treated as agreement or disagreement)."
        )
    return value, method


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_weather_intelligence(
    fusion_result: Optional[Dict[str, Any]] = None,
    single_source_record: Optional[Any] = None,
    single_source_name: Optional[str] = None,
    verification_results: Optional[List[Dict[str, Any]]] = None,
    max_time_diff_minutes: float = DEFAULT_MAX_TIME_DIFF_MINUTES,
    max_distance_km: float = DEFAULT_MAX_DISTANCE_KM,
) -> WeatherIntelligence:
    """Assembles one unified WeatherIntelligence record.

    Exactly one of `fusion_result` (a Phase 2B/2C fuse_pair()-shaped dict)
    or `single_source_record` (a single WeatherRecord, when only one
    observation source is available for this time/place) should be given.
    `verification_results` is the full list of Phase 3C verify_report()
    outputs to search for reports matching this record's time/location
    (via select_report_evidence(), which reuses Phase 2B's own alignment
    functions) -- pass None or [] if no report evidence should be attached.
    """
    verification_results = verification_results or []

    if fusion_result is not None:
        sources_dict = fusion_result.get("sources", {})
        contributing_sources = list(sources_dict.keys())
        # Timestamp/location: matched pairs share (within tolerance) the
        # same time/place by construction -- take them from the first
        # source, documented rather than silently assumed.
        first_source = next(iter(sources_dict.values()), {})
        timestamp = first_source.get("timestamp")
        latitude = first_source.get("latitude")
        longitude = first_source.get("longitude")
        location_source = first_source

        match_status = fusion_result.get("match_status")
        fusion = fusion_result.get("fusion", {}) or {}
        source_agreement_confidence = fusion.get("confidence_score")
        source_agreement_marginal = fusion.get("marginal_match")
        source_agreement_details = fusion_result.get("comparison", {})
        weather_variables = _weather_variables_from_fusion(fusion_result)

    elif single_source_record is not None:
        rec = single_source_record
        rec_dict = rec if isinstance(rec, dict) else rec.to_dict()
        name = single_source_name or rec_dict.get("source") or "UNKNOWN"
        contributing_sources = [name]
        timestamp = rec_dict.get("timestamp")
        latitude = rec_dict.get("latitude")
        longitude = rec_dict.get("longitude")
        location_source = rec_dict

        match_status = None       # single source -- no cross-source match to report
        source_agreement_confidence = None
        source_agreement_marginal = None
        source_agreement_details = {}
        weather_variables = _weather_variables_from_record(rec_dict)

    else:
        raise ValueError("build_weather_intelligence requires either fusion_result or single_source_record.")

    report_evidence = select_report_evidence(
        timestamp, latitude, longitude, verification_results,
        max_time_diff_minutes=max_time_diff_minutes, max_distance_km=max_distance_km,
    )
    corroboration_status, corroboration_reasons = rollup_corroboration_status(report_evidence)
    evidence_support_score = compute_evidence_support_score(report_evidence)
    overall_confidence, confidence_method = compute_overall_confidence(
        source_agreement_confidence, evidence_support_score
    )

    return WeatherIntelligence(
        timestamp=timestamp,
        latitude=latitude,
        longitude=longitude,
        country=location_source.get("country"),
        state=location_source.get("state"),
        district=location_source.get("district"),
        city=location_source.get("city"),
        weather_variables=weather_variables,
        contributing_sources=contributing_sources,
        source_agreement_confidence=source_agreement_confidence,
        source_agreement_match_status=match_status,
        source_agreement_details=source_agreement_details,
        source_agreement_marginal=source_agreement_marginal,
        report_evidence=report_evidence,
        corroboration_status=corroboration_status,
        corroboration_reasons=corroboration_reasons,
        evidence_support_score=evidence_support_score,
        overall_confidence=overall_confidence,
        confidence_method=confidence_method,
        forecast=None,
        anomaly=None,
        alert=None,
    )
