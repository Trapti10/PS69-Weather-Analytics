"""
Phase 3C -- Event -> Weather Evidence mapping.

Purpose: a transparent, documented lookup from a WeatherReport's normalized
`event_type` (Phase 3A's controlled vocabulary, src/schemas/weather_report.py
EVENT_TYPES) to the WeatherRecord (src/schemas/weather_record.py) fields that
can serve as evidence for or against that report's claim.

DESIGN RULE (per the Phase 3C spec, Part 1): this mapping must document,
for every event category, which variables are:
    - required   -- at least one of these must be available in a matched
                     WeatherRecord, or the report is INSUFFICIENT_EVIDENCE
    - supporting -- strengthens/weakens the read when available, but its
                     absence alone never forces INSUFFICIENT_EVIDENCE
    - unavailable -- variables that would be the *ideal* evidence for this
                     event category but do not exist anywhere in this
                     project's WeatherRecord schema or data sources. These
                     are named explicitly so nobody mistakes their absence
                     for "we forgot to check" -- the project's schema
                     genuinely does not carry them.

This module invents no data and adds no new WeatherRecord fields. It only
reads fields that already exist: temperature, humidity, pressure, rainfall,
wind_speed, wind_direction, plus `wind_gust` when present inside a record's
raw_payload (ERA5's `fg10`, Open-Meteo's `wind_gusts_10m` -- see
src/adapters/era5_adapter.py and src/adapters/openmeteo_adapter.py
docstrings). wind_gust is therefore listed as "supporting, raw_payload-only"
rather than a first-class WeatherRecord field.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EvidenceRequirement:
    event_category: str
    required: List[str]           # WeatherRecord field names (or "wind_gust" via raw_payload)
    supporting: List[str] = field(default_factory=list)
    unavailable: List[str] = field(default_factory=list)  # ideal evidence this schema does NOT carry
    notes: str = ""


# Documented, stated mapping -- not a scientific claim about which variables
# are the single "correct" indicator for an event; a reasonable, explainable
# starting point per the Phase 3C spec's own examples.
EVENT_EVIDENCE_MAP = {
    "RAINFALL": EvidenceRequirement(
        event_category="RAINFALL",
        required=["rainfall"],
        supporting=[],
        notes="Direct precipitation measurement is the only variable used.",
    ),
    "THUNDERSTORM": EvidenceRequirement(
        event_category="THUNDERSTORM",
        required=["rainfall"],
        supporting=["wind_speed", "wind_gust"],
        notes=(
            "Precipitation is required evidence. Wind speed/gust are supporting "
            "only (a thunderstorm can occur with modest sustained wind but a "
            "sharp gust); their absence does not by itself block a verdict."
        ),
    ),
    "FLOODING": EvidenceRequirement(
        event_category="FLOODING",
        required=["rainfall"],
        supporting=[],
        unavailable=["river_gauge_level", "drainage_capacity"],
        notes=(
            "Flooding is corroborated only indirectly, via rainfall -- this "
            "project has no river-gauge or drainage data. A rainfall-supported "
            "verdict here means 'consistent with a rain event', NOT confirmation "
            "that flooding specifically occurred."
        ),
    ),
    "HEATWAVE": EvidenceRequirement(
        event_category="HEATWAVE",
        required=["temperature"],
        supporting=[],
        notes="Direct temperature measurement is the only variable used.",
    ),
    "STRONG_WIND": EvidenceRequirement(
        event_category="STRONG_WIND",
        required=["wind_speed"],
        supporting=["wind_gust"],
        notes="Sustained wind speed is required; gust (raw_payload-only) is supporting.",
    ),
    "DUST_STORM": EvidenceRequirement(
        event_category="DUST_STORM",
        required=["wind_speed"],
        supporting=["wind_gust"],
        unavailable=["visibility", "aerosol_optical_depth"],
        notes=(
            "Dust storms are corroborated only via wind speed/gust -- this "
            "project has no visibility or aerosol/particulate data, so a "
            "supported verdict means 'consistent with strong wind', not "
            "confirmation of airborne dust specifically."
        ),
    ),
    "FOG": EvidenceRequirement(
        event_category="FOG",
        required=[],
        supporting=["humidity"],
        unavailable=["visibility_km"],
        notes=(
            "Fog has NO required variable in this mapping: humidity alone is a "
            "weak, indirect proxy (high humidity is necessary but not "
            "sufficient for fog), and this project's WeatherRecord schema has "
            "no visibility field, which would be the actually-diagnostic "
            "variable. Any FOG verdict is therefore capped at AMBIGUOUS/"
            "supporting-at-best and must never be reported as strong evidence."
        ),
    ),
    "OTHER": EvidenceRequirement(
        event_category="OTHER",
        required=[],
        supporting=[],
        notes="No defined evidence mapping for the catch-all 'OTHER' category.",
    ),
}


def get_evidence_requirements(event_category: Optional[str]) -> Optional[EvidenceRequirement]:
    """Returns the EvidenceRequirement for a normalized event_type, or None
    if the category is missing/unrecognized. Callers must treat None as an
    explicit 'no mapping exists' case, not silently fall back to a guess."""
    if event_category is None:
        return None
    return EVENT_EVIDENCE_MAP.get(event_category)
