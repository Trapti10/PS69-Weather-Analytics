"""
Phase 3C -- Multi-source evidence correlation.

For a single WeatherReport (Phase 3A/3B output), finds the best temporally
+spatially matched WeatherRecord in each configured evidence source (ERA5,
Open-Meteo, and IMD where compatible -- per the Phase 3C spec's Part 4),
then extracts whichever variables that report's event category actually
needs (src/corroboration/evidence_mapper.py).

This module does NOT decide SUPPORTED/CONFLICTING -- that judgment call is
verification_engine.py's job. This module only assembles the raw,
traceable per-source evidence: which record (if any) matched, how well it
matched, and what values it carried.

REAL DATA VS FIXTURE, EXPLICITLY LABELED (per Phase 3C spec Part 11 / 15):
- ERA5 evidence  (src="ERA5")       -> REAL Copernicus CDS reanalysis, 2024-2025.
- Open-Meteo evidence (src="Open-Meteo") -> REAL Open-Meteo historical archive,
  2024-2025, itself a MODEL/REANALYSIS BLEND -- never described as ground truth.
- IMD evidence (src="IMD")          -> Phase 2A's fixture-based WeatherRecord(s),
  dated around the fixture's creation time (2026), NOT genuine 2024-2025
  station observations. If a report's timestamp does not overlap this
  fixture's actual timestamp within tolerance, this module reports the
  explicit reason "IMD_TEMPORAL_UNAVAILABLE" rather than a generic
  TEMPORAL_MISMATCH, so downstream consumers can tell the difference between
  "IMD disagreed" and "IMD simply cannot speak to this period at all".
"""
from __future__ import annotations

import sys
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_record import WeatherRecord
from corroboration.temporal_evidence import (
    build_sorted_time_index, find_temporal_candidates, DEFAULT_MAX_TIME_DIFF_MINUTES,
)
from corroboration.spatial_evidence import evaluate_spatial_evidence, DEFAULT_MAX_DISTANCE_KM
from corroboration.evidence_mapper import get_evidence_requirements, EvidenceRequirement

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Real-data-vs-fixture labeling, stated once here rather than inferred --
# see module docstring. Callers (the demo script, tests) may register
# additional sources with their own explicit label.
DEFAULT_SOURCE_PATHS = {
    "ERA5": {
        "path": PROJECT_ROOT / "data" / "phase2" / "fused" / "era5_weather_records.json",
        "data_label": "REAL",  # Copernicus CDS reanalysis, 2024-2025
    },
    "Open-Meteo": {
        "path": PROJECT_ROOT / "data" / "phase2c" / "fused" / "openmeteo_weather_records.json",
        "data_label": "REAL",  # Open-Meteo historical archive, 2024-2025 (model/reanalysis blend)
    },
    "IMD": {
        "path": PROJECT_ROOT / "data" / "phase2" / "processed" / "weather_records.json",
        "data_label": "FIXTURE",  # Phase 2A fixture, dated ~2026, no genuine 2024-2025 overlap
    },
}


@dataclass
class EvidenceSource:
    name: str
    data_label: str  # "REAL" | "FIXTURE"
    records: List[WeatherRecord] = field(default_factory=list)
    sorted_time_index: list = field(default_factory=list)


def load_records_from_json(path: Path) -> List[WeatherRecord]:
    """Reconstructs WeatherRecord objects from a previously saved
    to_dict()-shaped JSON file (Phase 2B/2C's own storage output) --
    reused as-is rather than re-running the ERA5/Open-Meteo adapters over
    all 17,544 rows again for every Phase 3C session."""
    with open(path, "r") as f:
        raw = json.load(f)
    return [WeatherRecord(**item) for item in raw]


def build_evidence_source(name: str, path: Path, data_label: str) -> EvidenceSource:
    records = load_records_from_json(path)
    index = build_sorted_time_index(records)
    return EvidenceSource(name=name, data_label=data_label, records=records, sorted_time_index=index)


def build_default_evidence_sources() -> Dict[str, EvidenceSource]:
    """Loads the project's real Phase 2B/2C evidence plus the Phase 2A IMD
    fixture, using the paths/labels declared in DEFAULT_SOURCE_PATHS."""
    sources = {}
    for name, cfg in DEFAULT_SOURCE_PATHS.items():
        if not cfg["path"].exists():
            continue  # explicit absence, never fabricated as an empty-but-present source
        sources[name] = build_evidence_source(name, cfg["path"], cfg["data_label"])
    return sources


def _extract_variable(record: WeatherRecord, variable: str) -> Optional[float]:
    """Reads a variable from a WeatherRecord, including wind_gust which is
    NOT a first-class WeatherRecord field but is preserved in raw_payload
    by both the ERA5 and Open-Meteo adapters (see their docstrings)."""
    if variable == "wind_gust":
        payload = record.raw_payload or {}
        val = payload.get("wind_gust")
        if val is None:
            val = payload.get("fg10")  # ERA5's raw key for the same quantity
        return val
    return getattr(record, variable, None)


@dataclass
class SourceCorrelation:
    source_name: str
    data_label: str                      # "REAL" | "FIXTURE"
    matched: bool
    unavailable_reason: Optional[str]    # e.g. "IMD_TEMPORAL_UNAVAILABLE", "NO_CANDIDATE_RECORD", None
    temporal_alignment: Dict[str, Any]
    spatial_alignment: Dict[str, Any]
    matched_record_timestamp: Optional[str]
    values: Dict[str, Optional[float]]   # required+supporting variable values from the matched record


def correlate_report_with_source(report, source: EvidenceSource,
                                  requirement: EvidenceRequirement,
                                  max_time_diff_minutes: float = DEFAULT_MAX_TIME_DIFF_MINUTES,
                                  max_distance_km: float = DEFAULT_MAX_DISTANCE_KM) -> SourceCorrelation:
    if report.timestamp is None:
        return SourceCorrelation(
            source_name=source.name, data_label=source.data_label, matched=False,
            unavailable_reason="MISSING_REPORT_TIMESTAMP",
            temporal_alignment={"flag": "TEMPORAL_UNKNOWN"}, spatial_alignment={"flag": "SPATIAL_UNKNOWN"},
            matched_record_timestamp=None, values={},
        )

    temporal = find_temporal_candidates(
        report.timestamp, source.records, source.sorted_time_index, max_time_diff_minutes
    )

    if temporal.best_match_record_index is None:
        reason = "IMD_TEMPORAL_UNAVAILABLE" if source.name == "IMD" else "NO_TEMPORAL_MATCH"
        return SourceCorrelation(
            source_name=source.name, data_label=source.data_label, matched=False,
            unavailable_reason=reason,
            temporal_alignment=asdict_safe(temporal), spatial_alignment={"flag": "SPATIAL_UNKNOWN"},
            matched_record_timestamp=None, values={},
        )

    record = source.records[temporal.best_match_record_index]
    spatial = evaluate_spatial_evidence(report.latitude, report.longitude,
                                         record.latitude, record.longitude, max_distance_km)

    if spatial.flag != "SPATIAL_MATCH":
        reason = "MISSING_REPORT_LOCATION" if spatial.flag == "SPATIAL_INSUFFICIENT" else "NO_SPATIAL_MATCH"
        return SourceCorrelation(
            source_name=source.name, data_label=source.data_label, matched=False,
            unavailable_reason=reason,
            temporal_alignment=asdict_safe(temporal), spatial_alignment=asdict_safe(spatial),
            matched_record_timestamp=record.timestamp, values={},
        )

    all_vars = list(dict.fromkeys(requirement.required + requirement.supporting))
    values = {v: _extract_variable(record, v) for v in all_vars}

    return SourceCorrelation(
        source_name=source.name, data_label=source.data_label, matched=True,
        unavailable_reason=None,
        temporal_alignment=asdict_safe(temporal), spatial_alignment=asdict_safe(spatial),
        matched_record_timestamp=record.timestamp, values=values,
    )


def asdict_safe(obj) -> Dict[str, Any]:
    try:
        return asdict(obj)
    except TypeError:
        return dict(obj) if isinstance(obj, dict) else {"value": obj}


def correlate_report(report, evidence_sources: Dict[str, EvidenceSource],
                      max_time_diff_minutes: float = DEFAULT_MAX_TIME_DIFF_MINUTES,
                      max_distance_km: float = DEFAULT_MAX_DISTANCE_KM) -> Dict[str, Any]:
    """Correlates one WeatherReport against every configured evidence
    source. Returns a dict keyed by source name -> SourceCorrelation, plus
    the EvidenceRequirement used (or None if the event category has no
    mapping / report has no event category at all)."""
    requirement = get_evidence_requirements(report.event_type)

    if requirement is None:
        return {"requirement": None, "sources": {}}

    results = {}
    for name, source in evidence_sources.items():
        results[name] = correlate_report_with_source(
            report, source, requirement, max_time_diff_minutes, max_distance_km
        )
    return {"requirement": requirement, "sources": results}
