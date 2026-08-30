"""
Fusion engine: orchestrates temporal alignment -> spatial alignment ->
source comparison -> confidence-scored fusion for a pair of records from
different sources (currently ERA5 and IMD; designed to generalize -- see
module docstring at bottom).

CONFIDENCE SCORE -- called "source_agreement_confidence", NOT a claim of
real-world meteorological certainty (per Part 6's explicit instruction).

Exact calculation, documented step by step:
1. If temporal or spatial match fails (or is unknown), fusion is NOT
   attempted for that record pair. No confidence score is fabricated for
   an unmatched pair -- the pair is returned with match_status describing
   why, and fusion.per_variable is empty.
2. For each variable with a valid comparison (SOURCE_COMPARISON_UNAVAILABLE
   is skipped), convert its agreement flag to a numeric score:
       SOURCE_AGREEMENT_HIGH   -> 1.0
       SOURCE_AGREEMENT_MEDIUM -> 0.6
       SOURCE_DISAGREEMENT     -> 0.2
3. record_confidence = mean of all per-variable scores for this pair.
4. If the spatial or temporal match is only "marginal" (within the
   tolerance but past 70% of it), record_confidence is reduced by a
   further 10% -- a match just inside a 60-minute/25km window is less
   trustworthy than one well inside it. This is a deliberately simple,
   documented rule, not a statistically fitted one.
5. Per variable: fused_value = mean(era5_value, imd_value) ONLY if that
   variable's agreement is HIGH or MEDIUM. On SOURCE_DISAGREEMENT, fused
   value is explicitly None and BOTH raw values are preserved -- per
   Part 7's explicit instruction not to blindly average disagreements.

This module works on any two WeatherRecord objects and is not hardcoded to
ERA5+IMD by name in its core functions (fuse_pair takes two generic records
and two source-name labels) -- extending to a third source means calling
compare/fuse pairwise and combining, not rewriting this module. See
README Phase 2B section for the scaling discussion.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

from fusion.temporal_alignment import check_temporal_match, DEFAULT_MAX_TIME_DIFF_MINUTES
from fusion.spatial_alignment import check_spatial_match, DEFAULT_MAX_DISTANCE_KM
from fusion.source_comparison import compare_records

AGREEMENT_SCORE = {
    "SOURCE_AGREEMENT_HIGH": 1.0,
    "SOURCE_AGREEMENT_MEDIUM": 0.6,
    "SOURCE_DISAGREEMENT": 0.2,
}

MARGINAL_FRACTION = 0.7  # a match past 70% of the allowed tolerance is "marginal"
MARGINAL_PENALTY = 0.9   # multiply confidence by this if either match is marginal


def fuse_pair(record_a, record_b, label_a: str = "ERA5", label_b: str = "IMD",
              max_time_diff_minutes: float = DEFAULT_MAX_TIME_DIFF_MINUTES,
              max_distance_km: float = DEFAULT_MAX_DISTANCE_KM) -> Dict[str, Any]:
    """Fuse two WeatherRecords from different sources into a transparent,
    traceable comparison+fusion result. Returns a plain dict matching the
    shape described in the Phase-2B spec (sources/comparison/fusion keys)."""

    temporal = check_temporal_match(record_a.timestamp, record_b.timestamp, max_time_diff_minutes)
    spatial = check_spatial_match(record_a.latitude, record_a.longitude,
                                   record_b.latitude, record_b.longitude, max_distance_km)

    result: Dict[str, Any] = {
        "sources": {
            label_a: record_a.to_dict(),
            label_b: record_b.to_dict(),
        },
        "temporal_alignment": asdict(temporal),
        "spatial_alignment": asdict(spatial),
    }

    if not temporal.is_match or not spatial.is_match:
        result["match_status"] = "NOT_MATCHED"
        result["comparison"] = {}
        result["fusion"] = {
            "note": "Fusion not attempted: records are not temporally/spatially matched.",
            "confidence_score": None,
        }
        return result

    result["match_status"] = "MATCHED"

    comparisons = compare_records(record_a, record_b)
    key_a, key_b = f"{label_a.lower()}_value", f"{label_b.lower()}_value"
    result["comparison"] = {
        var: {
            key_a: c.era5_value,   # value from record_a (named after label_a, whatever it is)
            key_b: c.imd_value,    # value from record_b (named after label_b, whatever it is)
            "absolute_difference": c.absolute_difference,
            "percent_difference": c.percent_difference,
            "agreement_flag": c.agreement_flag,
        }
        for var, c in comparisons.items()
    }

    scored = [AGREEMENT_SCORE[c.agreement_flag] for c in comparisons.values()
              if c.agreement_flag in AGREEMENT_SCORE]
    base_confidence = sum(scored) / len(scored) if scored else None

    marginal = False
    if temporal.time_difference_minutes is not None and max_time_diff_minutes > 0:
        marginal = marginal or (temporal.time_difference_minutes > MARGINAL_FRACTION * max_time_diff_minutes)
    if spatial.distance_km is not None and max_distance_km > 0:
        marginal = marginal or (spatial.distance_km > MARGINAL_FRACTION * max_distance_km)

    confidence = base_confidence
    if confidence is not None and marginal:
        confidence = round(confidence * MARGINAL_PENALTY, 4)
    elif confidence is not None:
        confidence = round(confidence, 4)

    fused_values = {}
    for var, c in comparisons.items():
        if c.agreement_flag in ("SOURCE_AGREEMENT_HIGH", "SOURCE_AGREEMENT_MEDIUM"):
            fused_values[var] = round((c.era5_value + c.imd_value) / 2, 3)
        elif c.agreement_flag == "SOURCE_DISAGREEMENT":
            fused_values[var] = None  # explicitly not averaged -- see module docstring
        # SOURCE_COMPARISON_UNAVAILABLE variables are omitted from fused_values entirely

    result["fusion"] = {
        **fused_values,
        "confidence_score": confidence,
        "confidence_label": "source_agreement_confidence",  # NOT a meteorological certainty claim
        "marginal_match": marginal,
    }

    return result
