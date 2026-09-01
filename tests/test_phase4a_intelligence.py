"""
Tests for Phase 4A: the unified WeatherIntelligence layer.

Runs entirely offline. Uses small, hand-authored, in-memory fixtures
(fuse_pair()-shaped fusion results, single WeatherRecords, and
verify_report()-shaped verification results) so every behavior under test
is deterministic and does not depend on the real 17,544-row ERA5/Open-Meteo
series or the real Phase 3C demo output. See scripts/run_phase4a_demo.py
for the real-data end-to-end demonstration.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from schemas.weather_record import WeatherRecord

from phase4.weather_intelligence import (
    WeatherIntelligence,
    build_weather_intelligence,
    select_report_evidence,
    rollup_corroboration_status,
    compute_evidence_support_score,
    compute_overall_confidence,
    WEATHER_VARIABLE_KEYS,
)
from phase4.intelligence_storage import (
    save_weather_intelligence_json, save_weather_intelligence_csv, load_weather_intelligence_json,
    PHASE4_DIR,
)


# ---------------------------------------------------------------------------
# Fixtures (small, hand-authored, clearly synthetic -- not presented as real)
# ---------------------------------------------------------------------------

def make_fusion_result(confidence=0.8, match_status="MATCHED", marginal=False,
                        timestamp="2024-06-01T12:00:00Z", lat=23.25, lon=80.0,
                        temperature=30.0, rainfall=0.0):
    era5 = {"source": "ERA5", "timestamp": timestamp, "latitude": lat, "longitude": lon,
            "country": "India", "state": None, "district": None, "city": None}
    openmeteo = {"source": "Open-Meteo", "timestamp": timestamp, "latitude": lat, "longitude": lon,
                 "country": "India", "state": None, "district": None, "city": None}
    return {
        "sources": {"ERA5": era5, "Open-Meteo": openmeteo},
        "match_status": match_status,
        "comparison": {
            "temperature": {"agreement_flag": "SOURCE_AGREEMENT_HIGH"},
        },
        "fusion": {
            "temperature": temperature,
            "humidity": None,
            "pressure": None,
            "rainfall": rainfall,
            "wind_speed": None,
            "wind_direction": None,
            "confidence_score": confidence,
            "confidence_label": "source_agreement_confidence",
            "marginal_match": marginal,
        } if match_status == "MATCHED" else {"note": "not matched", "confidence_score": None},
    }


def make_verification_result(report_id, status, score, timestamp="2024-06-01T12:00:00Z",
                              lat=23.25, lon=80.0, event_category="HEATWAVE"):
    return {
        "report_id": report_id,
        "event_category": event_category,
        "verification_status": status,
        "evidence_support_score": score,
        "risk_label": "LOW_RISK",
        "risk_score": 0.1,
        "report_timestamp": timestamp,
        "latitude": lat,
        "longitude": lon,
    }


def make_single_record(temperature=25.0, rainfall=1.2, timestamp="2024-03-01T00:00:00Z"):
    return WeatherRecord(
        source="ERA5", timestamp=timestamp, latitude=23.25, longitude=80.0,
        temperature=temperature, rainfall=rainfall,
    )


# ---------------------------------------------------------------------------
# 1. Creation of a WeatherIntelligence object
# ---------------------------------------------------------------------------

def test_weather_intelligence_object_creates_with_defaults():
    wi = WeatherIntelligence()
    assert wi.id is not None
    assert wi.timestamp is None
    assert wi.weather_variables == {}
    assert wi.contributing_sources == []
    assert wi.corroboration_status is None
    assert wi.forecast is None
    assert wi.anomaly is None
    assert wi.alert is None


# ---------------------------------------------------------------------------
# 2. Single-source weather data
# ---------------------------------------------------------------------------

def test_single_source_record_populates_variables_and_no_agreement_score():
    record = make_single_record(temperature=25.0, rainfall=1.2)
    wi = build_weather_intelligence(single_source_record=record, verification_results=[])

    assert wi.contributing_sources == ["ERA5"]
    assert wi.weather_variables["temperature"] == 25.0
    assert wi.weather_variables["rainfall"] == 1.2
    # single source -- nothing to agree/disagree on
    assert wi.source_agreement_confidence is None
    assert wi.source_agreement_match_status is None


# ---------------------------------------------------------------------------
# 3. Multi-source / fused weather data
# ---------------------------------------------------------------------------

def test_fused_multi_source_record_populates_variables_and_agreement():
    fusion = make_fusion_result(confidence=0.85, temperature=41.0)
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=[])

    assert set(wi.contributing_sources) == {"ERA5", "Open-Meteo"}
    assert wi.weather_variables["temperature"] == 41.0
    assert wi.source_agreement_confidence == 0.85
    assert wi.source_agreement_match_status == "MATCHED"


def test_fused_disagreement_variable_stays_none_not_averaged():
    fusion = make_fusion_result(confidence=0.5)
    fusion["fusion"]["rainfall"] = None  # simulates a SOURCE_DISAGREEMENT variable
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=[])
    assert wi.weather_variables["rainfall"] is None


# ---------------------------------------------------------------------------
# 4. Source provenance
# ---------------------------------------------------------------------------

def test_contributing_sources_reflects_actual_inputs():
    fusion = make_fusion_result()
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=[])
    assert "ERA5" in wi.contributing_sources
    assert "Open-Meteo" in wi.contributing_sources
    assert "IMD" not in wi.contributing_sources


# ---------------------------------------------------------------------------
# 5. Corroboration status (rollup mechanics directly)
# ---------------------------------------------------------------------------

def test_rollup_supported_only():
    evidence = [{"verification_status": "SUPPORTED"}, {"verification_status": "SUPPORTED"}]
    status, reasons = rollup_corroboration_status(evidence)
    assert status == "SUPPORTED"
    assert reasons


# ---------------------------------------------------------------------------
# 6. Supported evidence, end to end
# ---------------------------------------------------------------------------

def test_end_to_end_supported():
    fusion = make_fusion_result(confidence=0.9, temperature=41.0)
    verifications = [make_verification_result("R1", "SUPPORTED", 1.0)]
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=verifications)

    assert wi.corroboration_status == "SUPPORTED"
    assert len(wi.report_evidence) == 1
    assert wi.evidence_support_score == 1.0
    assert wi.overall_confidence == round((0.9 + 1.0) / 2, 4)


# ---------------------------------------------------------------------------
# 7. Conflicting evidence -- both directly and via rollup disagreement
# ---------------------------------------------------------------------------

def test_conflicting_evidence_status():
    fusion = make_fusion_result(confidence=0.7)
    verifications = [make_verification_result("R2", "CONFLICTING", 0.0)]
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=verifications)
    assert wi.corroboration_status == "CONFLICTING"
    assert wi.evidence_support_score == 0.0


def test_rollup_disagreement_between_reports_becomes_conflicting_not_averaged():
    evidence = [
        {"verification_status": "SUPPORTED"},
        {"verification_status": "CONFLICTING"},
    ]
    status, reasons = rollup_corroboration_status(evidence)
    assert status == "CONFLICTING"
    assert any("disagree" in r.lower() for r in reasons)


# ---------------------------------------------------------------------------
# 8. Unverified evidence
# ---------------------------------------------------------------------------

def test_unverified_evidence_status():
    fusion = make_fusion_result(confidence=0.6)
    verifications = [make_verification_result("R3", "UNVERIFIED", 0.5)]
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=verifications)
    assert wi.corroboration_status == "UNVERIFIED"


# ---------------------------------------------------------------------------
# 9. Insufficient evidence
# ---------------------------------------------------------------------------

def test_no_matching_reports_gives_insufficient_evidence():
    fusion = make_fusion_result(confidence=0.6)
    # A verification result far away in time -- should not match.
    verifications = [make_verification_result("R4", "SUPPORTED", 1.0, timestamp="2020-01-01T00:00:00Z")]
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=verifications)
    assert wi.corroboration_status == "INSUFFICIENT_EVIDENCE"
    assert wi.report_evidence == []
    assert wi.evidence_support_score is None


def test_empty_verification_results_gives_insufficient_evidence():
    fusion = make_fusion_result(confidence=0.6)
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=[])
    assert wi.corroboration_status == "INSUFFICIENT_EVIDENCE"


def test_all_matched_reports_insufficient_rolls_up_to_insufficient():
    evidence = [{"verification_status": "INSUFFICIENT_EVIDENCE"}, {"verification_status": "INSUFFICIENT_EVIDENCE"}]
    status, _ = rollup_corroboration_status(evidence)
    assert status == "INSUFFICIENT_EVIDENCE"


# ---------------------------------------------------------------------------
# 10. Confidence calculation
# ---------------------------------------------------------------------------

def test_overall_confidence_mean_of_both_when_both_present():
    value, method = compute_overall_confidence(0.8, 0.4)
    assert value == 0.6
    assert "mean" in method.lower()


def test_overall_confidence_equals_single_input_when_only_one_present():
    value, method = compute_overall_confidence(0.8, None)
    assert value == 0.8
    value2, method2 = compute_overall_confidence(None, 0.4)
    assert value2 == 0.4


def test_evidence_support_score_is_transparent_mean():
    evidence = [
        {"evidence_support_score": 1.0},
        {"evidence_support_score": 0.0},
    ]
    assert compute_evidence_support_score(evidence) == 0.5


# ---------------------------------------------------------------------------
# 11. Missing confidence -- never fabricated
# ---------------------------------------------------------------------------

def test_overall_confidence_is_none_when_both_inputs_missing():
    value, method = compute_overall_confidence(None, None)
    assert value is None
    assert "not fabricated" in method.lower()


def test_evidence_support_score_none_when_no_report_has_a_score():
    evidence = [{"evidence_support_score": None}]
    assert compute_evidence_support_score(evidence) is None


def test_single_source_record_with_no_report_evidence_has_no_overall_confidence():
    record = make_single_record()
    wi = build_weather_intelligence(single_source_record=record, verification_results=[])
    assert wi.overall_confidence is None
    assert wi.source_agreement_confidence is None
    assert wi.evidence_support_score is None


# ---------------------------------------------------------------------------
# 12. Missing / unmatched fusion
# ---------------------------------------------------------------------------

def test_not_matched_fusion_result_has_no_agreement_confidence():
    fusion = make_fusion_result(match_status="NOT_MATCHED")
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=[])
    assert wi.source_agreement_match_status == "NOT_MATCHED"
    assert wi.source_agreement_confidence is None
    # unavailable evidence must never be treated as agreement
    assert wi.overall_confidence is None


def test_build_requires_fusion_or_single_source():
    try:
        build_weather_intelligence()
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_select_report_evidence_requires_timestamp_and_location():
    assert select_report_evidence(None, 23.25, 80.0, [make_verification_result("R", "SUPPORTED", 1.0)]) == []
    assert select_report_evidence("2024-06-01T12:00:00Z", None, 80.0, [make_verification_result("R", "SUPPORTED", 1.0)]) == []


# ---------------------------------------------------------------------------
# 13. Serialization / deserialization
# ---------------------------------------------------------------------------

def test_to_dict_and_from_dict_round_trip():
    fusion = make_fusion_result(confidence=0.9, temperature=41.0)
    verifications = [make_verification_result("R5", "SUPPORTED", 1.0)]
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=verifications)

    d = wi.to_dict()
    assert d["corroboration_status"] == "SUPPORTED"
    assert d["weather_variables"]["temperature"] == 41.0

    restored = WeatherIntelligence.from_dict(d)
    assert restored.id == wi.id
    assert restored.corroboration_status == wi.corroboration_status
    assert restored.overall_confidence == wi.overall_confidence
    assert restored.weather_variables == wi.weather_variables


def test_from_dict_ignores_unknown_keys():
    d = WeatherIntelligence().to_dict()
    d["some_future_field_not_yet_defined"] = "anything"
    restored = WeatherIntelligence.from_dict(d)
    assert isinstance(restored, WeatherIntelligence)


# ---------------------------------------------------------------------------
# 14. Storage round-trip
# ---------------------------------------------------------------------------

def test_storage_round_trip_json():
    fusion = make_fusion_result(confidence=0.9, temperature=41.0)
    verifications = [make_verification_result("R6", "SUPPORTED", 1.0)]
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=verifications)

    path = save_weather_intelligence_json([wi], filename="_test_weather_intelligence.json")
    assert path.exists()
    assert path.parent == PHASE4_DIR

    loaded = load_weather_intelligence_json(filename="_test_weather_intelligence.json")
    assert len(loaded) == 1
    assert loaded[0].id == wi.id
    assert loaded[0].corroboration_status == "SUPPORTED"
    assert loaded[0].weather_variables["temperature"] == 41.0

    path.unlink()  # clean up the test artifact, leave real demo outputs alone


def test_storage_round_trip_csv():
    fusion = make_fusion_result(confidence=0.9, temperature=41.0)
    verifications = [make_verification_result("R7", "CONFLICTING", 0.0)]
    wi = build_weather_intelligence(fusion_result=fusion, verification_results=verifications)

    path = save_weather_intelligence_csv([wi], filename="_test_weather_intelligence.csv")
    assert path.exists()
    content = path.read_text()
    assert "CONFLICTING" in content
    assert "R7" in content

    path.unlink()


# ---------------------------------------------------------------------------
# Extra: weather-variable key set matches the project's existing schema
# ---------------------------------------------------------------------------

def test_weather_variable_keys_match_weather_record_schema():
    record_fields = set(WeatherRecord().to_dict().keys())
    for key in WEATHER_VARIABLE_KEYS:
        assert key in record_fields, f"{key} is not a real WeatherRecord field"
