"""
Tests for Phase 3C: event->evidence mapping, temporal/spatial evidence
lookup, multi-source correlation, and the verification engine.

Runs entirely offline. Uses TWO kinds of fixtures, deliberately kept
separate and labeled:
  (a) REAL Phase 2B/2C evidence already on disk (era5_weather_records.json,
      openmeteo_weather_records.json) -- used wherever a real data point
      naturally demonstrates the behavior under test (e.g. the real
      2024-09-10 rainfall peak, the real 2024-06-01 hot day).
  (b) Small, hand-authored, in-memory synthetic WeatherRecord/EvidenceSource
      fixtures -- used for behaviors that require values outside this
      project's real observed range (e.g. sustained wind_speed >= 10.8 m/s,
      which never actually occurs in the real 2024-2025 Jabalpur data --
      see verification_engine.py's VARIABLE_THRESHOLDS) or that need a
      guaranteed multi-source disagreement.
Every synthetic record built here is clearly a test fixture, not presented
as real data anywhere outside this file.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from schemas.weather_record import WeatherRecord
from schemas.weather_report import WeatherReport

from corroboration.evidence_mapper import get_evidence_requirements, EVENT_EVIDENCE_MAP
from corroboration.temporal_evidence import build_sorted_time_index, find_temporal_candidates
from corroboration.spatial_evidence import evaluate_spatial_evidence
from corroboration.report_correlator import (
    build_default_evidence_sources, correlate_report, EvidenceSource,
)
from corroboration.verification_engine import (
    evaluate_variable_value, verify_report, VARIABLE_THRESHOLDS,
)

# ---- Real Phase 2B/2C evidence, loaded once for the whole test module ----
EVIDENCE_SOURCES = build_default_evidence_sources()

JABALPUR_LAT, JABALPUR_LON = 23.25, 80.00  # matches ERA5's real grid point


def _mk_report(**overrides) -> WeatherReport:
    defaults = dict(
        report_id="test-report",
        source_type="PUBLIC_DATASET",
        event_type="RAINFALL",
        timestamp="2024-09-10T21:00:00Z",
        latitude=JABALPUR_LAT, longitude=JABALPUR_LON,
        text="[TEST FIXTURE]",
    )
    defaults.update(overrides)
    return WeatherReport(**defaults)


def _mk_fixture_evidence_source(name: str, records: list, data_label: str = "FIXTURE") -> EvidenceSource:
    return EvidenceSource(name=name, data_label=data_label, records=records,
                           sorted_time_index=build_sorted_time_index(records))


# ---------- 1. Evidence mapping is transparent and complete ----------
def test_evidence_mapping_covers_all_report_event_types():
    from schemas.weather_report import EVENT_TYPES
    for event_type in EVENT_TYPES:
        assert event_type in EVENT_EVIDENCE_MAP, f"missing evidence mapping for {event_type}"


def test_unmapped_event_category_returns_none():
    assert get_evidence_requirements("NOT_A_REAL_CATEGORY") is None
    assert get_evidence_requirements(None) is None


# ---------- 2. Supported rainfall report (REAL evidence) ----------
def test_supported_rainfall_report_real_data():
    """2024-09-10T21:00:00Z is the real ERA5 rainfall peak (20.9mm); Open-Meteo
    also shows real measurable rainfall (1.8mm) at the same real hour."""
    report = _mk_report(report_id="rain-support", event_type="RAINFALL",
                         timestamp="2024-09-10T21:00:00Z")
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    assert result["verification_status"] == "SUPPORTED"
    assert result["evidence_support_score"] == 1.0
    assert "ERA5" in result["evidence_sources"]
    assert "Open-Meteo" in result["evidence_sources"]


# ---------- 3. Conflicting rainfall report (REAL evidence) ----------
def test_conflicting_rainfall_report_real_data():
    """2024-01-15T09:00:00Z: a real dry-season hour with ~0mm rainfall in
    both real sources."""
    report = _mk_report(report_id="rain-conflict", event_type="RAINFALL",
                         timestamp="2024-01-15T09:00:00Z")
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    assert result["verification_status"] == "CONFLICTING"
    assert result["evidence_support_score"] == 0.0


# ---------- 4. Heatwave evidence (REAL evidence) ----------
def test_heatwave_supported_real_data():
    """2024-06-01T12:00:00Z: real peak-summer midday hour, both real sources
    report >=40C."""
    report = _mk_report(report_id="heatwave", event_type="HEATWAVE",
                         timestamp="2024-06-01T12:00:00Z")
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    assert result["verification_status"] == "SUPPORTED"
    for src in ("ERA5", "Open-Meteo"):
        assert result["source_evidence"][src]["values"]["temperature"] >= 40.0


# ---------- 5. Strong wind evidence (SYNTHETIC fixture -- real 2024-2025
#              Jabalpur wind speed never reaches the 10.8 m/s threshold,
#              see VARIABLE_THRESHOLDS's documented rationale) ----------
def test_strong_wind_evidence_synthetic_fixture():
    fixture_record = WeatherRecord(
        source="TEST_FIXTURE_SOURCE", timestamp="2024-05-01T12:00:00Z",
        latitude=JABALPUR_LAT, longitude=JABALPUR_LON, wind_speed=15.5,
    )
    source = _mk_fixture_evidence_source("TestWindSource", [fixture_record])
    report = _mk_report(report_id="strong-wind", event_type="STRONG_WIND",
                         timestamp="2024-05-01T12:00:00Z")
    result = verify_report(report, correlate_report(report, {"TestWindSource": source}))
    assert result["verification_status"] == "SUPPORTED"
    assert result["source_evidence"]["TestWindSource"]["values"]["wind_speed"] == 15.5


# ---------- 6. Multiple-source agreement (REAL evidence) ----------
def test_multi_source_agreement_both_real_sources_support():
    report = _mk_report(report_id="agree", event_type="RAINFALL",
                         timestamp="2024-09-10T21:00:00Z")
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    era5_val = result["source_evidence"]["ERA5"]["values"]["rainfall"]
    om_val = result["source_evidence"]["Open-Meteo"]["values"]["rainfall"]
    assert era5_val >= VARIABLE_THRESHOLDS["rainfall"]["support_min"]
    assert om_val >= VARIABLE_THRESHOLDS["rainfall"]["support_min"]
    assert result["verification_status"] == "SUPPORTED"


# ---------- 7. Multiple-source disagreement (REAL evidence, real hour where
#              ERA5 shows measurable rain but Open-Meteo shows none) ----------
def test_multi_source_disagreement_real_data():
    report = _mk_report(report_id="disagree", event_type="RAINFALL",
                         timestamp="2024-01-05T15:00:00Z")
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    era5_val = result["source_evidence"]["ERA5"]["values"]["rainfall"]
    om_val = result["source_evidence"]["Open-Meteo"]["values"]["rainfall"]
    assert era5_val >= VARIABLE_THRESHOLDS["rainfall"]["support_min"]
    assert om_val <= VARIABLE_THRESHOLDS["rainfall"]["conflict_max"]
    # Sources disagree -> UNVERIFIED, never silently averaged into SUPPORTED/CONFLICTING
    assert result["verification_status"] == "UNVERIFIED"
    assert any("disagree" in reason for reason in result["verification_reasons"])


# ---------- 8. Temporal mismatch ----------
def test_temporal_mismatch_outside_real_evidence_window():
    """Phase 3A's own real fixture timestamp style (2026) has no overlap
    with the real 2024-2025 evidence at all."""
    report = _mk_report(report_id="temporal-mismatch", event_type="RAINFALL",
                         timestamp="2026-07-14T10:32:00Z")
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    assert result["verification_status"] == "INSUFFICIENT_EVIDENCE"
    assert result["source_evidence"]["ERA5"]["unavailable_reason"] == "NO_TEMPORAL_MATCH"
    assert result["source_evidence"]["Open-Meteo"]["unavailable_reason"] == "NO_TEMPORAL_MATCH"


# ---------- 9. Spatial mismatch ----------
def test_spatial_mismatch_far_away_location():
    """A real timestamp (so temporal alignment succeeds) but a location far
    from Jabalpur (Kanyakumari, ~1500km south) -- must fail spatially, not
    be silently treated as a match."""
    report = _mk_report(report_id="spatial-mismatch", event_type="RAINFALL",
                         timestamp="2024-09-10T21:00:00Z", latitude=8.08, longitude=77.55)
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    assert result["verification_status"] == "INSUFFICIENT_EVIDENCE"
    assert result["source_evidence"]["ERA5"]["unavailable_reason"] == "NO_SPATIAL_MATCH"


# ---------- 10. Missing location ----------
def test_missing_location_is_explicit_insufficient_evidence():
    report = _mk_report(report_id="no-location", latitude=None, longitude=None)
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    assert result["verification_status"] == "INSUFFICIENT_EVIDENCE"
    assert "location" in result["verification_reasons"][0].lower()
    # Never silently assumes a location -- correlate_report never even
    # attempts a source lookup for a report with no location.
    assert result["source_evidence"] == {}


# ---------- 11. Missing timestamp ----------
def test_missing_timestamp_is_explicit_insufficient_evidence():
    report = _mk_report(report_id="no-timestamp", timestamp=None)
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    assert result["verification_status"] == "INSUFFICIENT_EVIDENCE"
    assert "timestamp" in result["verification_reasons"][0].lower()
    assert result["source_evidence"] == {}


# ---------- 12. Missing weather variable (no evidence mapping for OTHER) ----------
def test_other_event_category_has_no_mapping_and_is_insufficient():
    report = _mk_report(report_id="other-category", event_type="OTHER")
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    assert result["verification_status"] == "INSUFFICIENT_EVIDENCE"
    # OTHER has a mapping entry but deliberately no required/supporting
    # variables at all (see evidence_mapper.py) -- distinct from a
    # completely unmapped/unrecognized category.
    assert "no required or supporting variable defined" in result["verification_reasons"][0].lower()


def test_unrecognized_event_category_has_no_mapping_and_is_insufficient():
    """Distinct from OTHER (which has a mapping entry with empty variable
    lists): a category not in EVENT_EVIDENCE_MAP at all must hit the
    'no evidence mapping exists' path, not the 'no variable defined' path."""
    report = WeatherReport(report_id="bad-category", event_type="NOT_A_REAL_CATEGORY",
                            timestamp="2024-09-10T21:00:00Z", latitude=JABALPUR_LAT, longitude=JABALPUR_LON)
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    assert result["verification_status"] == "INSUFFICIENT_EVIDENCE"
    assert "no evidence mapping exists" in result["verification_reasons"][0].lower()


# ---------- 13. IMD unavailable due to temporal mismatch ----------
def test_imd_marked_temporally_unavailable_not_generic_mismatch():
    """Per the Phase 3C spec: IMD's Phase 2A fixture (dated ~2026) must never
    be silently treated as covering the real 2024-2025 evidence window --
    any real-dated report must get the explicit IMD_TEMPORAL_UNAVAILABLE
    reason, distinct from a generic NO_TEMPORAL_MATCH."""
    report = _mk_report(report_id="imd-check", event_type="RAINFALL",
                         timestamp="2024-09-10T21:00:00Z")
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    assert result["source_evidence"]["IMD"]["unavailable_reason"] == "IMD_TEMPORAL_UNAVAILABLE"
    assert result["source_evidence"]["IMD"]["matched"] is False
    assert "IMD" not in result["evidence_sources"]


# ---------- 14. Phase 3B prediction preserved, never overwritten ----------
def test_phase3b_fields_preserved_not_overwritten():
    report = _mk_report(
        report_id="phase3b-preserved", event_type="RAINFALL",
        timestamp="2024-09-10T21:00:00Z",
        predicted_event_category="RAINFALL", event_classification_confidence=0.28,
        risk_label="MEDIUM_RISK", risk_score=0.5,
    )
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    assert result["predicted_event_category"] == "RAINFALL"
    assert result["event_classification_confidence"] == 0.28
    assert result["risk_label"] == "MEDIUM_RISK"
    assert result["risk_score"] == 0.5
    # Phase 3C's own verdict is a SEPARATE field, does not touch the above
    assert result["verification_status"] == "SUPPORTED"


# ---------- 15. Explanation/reason fields always present and non-empty ----------
def test_verification_reasons_always_present_and_non_empty():
    cases = [
        _mk_report(report_id="r1", timestamp="2024-09-10T21:00:00Z"),
        _mk_report(report_id="r2", timestamp=None),
        _mk_report(report_id="r3", latitude=None, longitude=None),
        _mk_report(report_id="r4", event_type="OTHER"),
    ]
    for report in cases:
        result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
        assert isinstance(result["verification_reasons"], list)
        assert len(result["verification_reasons"]) >= 1
        assert all(isinstance(reason, str) and reason for reason in result["verification_reasons"])


# ---------- 16. Evidence traceability: every matched source is fully traceable ----------
def test_evidence_traceability_fields_present():
    report = _mk_report(report_id="traceability", event_type="RAINFALL",
                         timestamp="2024-09-10T21:00:00Z")
    result = verify_report(report, correlate_report(report, EVIDENCE_SOURCES))
    for src_name in ("ERA5", "Open-Meteo"):
        ev = result["source_evidence"][src_name]
        assert ev["matched"] is True
        assert ev["matched_record_timestamp"] == "2024-09-10T21:00:00Z"
        assert "rainfall" in ev["values"]
        assert result["temporal_alignment"][src_name]["flag"] == "TEMPORAL_MATCH"
        assert result["spatial_alignment"][src_name]["flag"] == "SPATIAL_MATCH"
    assert result["evidence_mapping_notes"]  # non-empty documentation string


# ---------- Extra: pure per-variable threshold logic (no I/O at all) ----------
def test_evaluate_variable_value_thresholds():
    assert evaluate_variable_value("rainfall", 5.0) == "SUPPORTING_EVIDENCE"
    assert evaluate_variable_value("rainfall", 0.0) == "CONFLICTING_EVIDENCE"
    assert evaluate_variable_value("rainfall", 0.3) == "AMBIGUOUS_EVIDENCE"
    assert evaluate_variable_value("rainfall", None) == "VARIABLE_UNAVAILABLE"
    assert evaluate_variable_value("not_a_real_variable", 5.0) == "VARIABLE_UNAVAILABLE"


# ---------- Extra: temporal candidate counting behaves sanely on real data ----------
def test_temporal_candidate_count_on_real_era5_series():
    era5_source = EVIDENCE_SOURCES["ERA5"]
    result = find_temporal_candidates("2024-09-10T21:00:00Z", era5_source.records,
                                       era5_source.sorted_time_index, max_time_diff_minutes=90.0)
    assert result.temporal_match is True
    assert result.time_difference_minutes == 0.0
    assert result.candidate_record_count >= 1


# ---------- Extra: spatial evaluation never assumes a match with no report location ----------
def test_spatial_evidence_missing_report_location_is_explicit():
    result = evaluate_spatial_evidence(None, None, JABALPUR_LAT, JABALPUR_LON)
    assert result.flag == "SPATIAL_INSUFFICIENT"
    assert result.spatial_match is False


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL: {t.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
