"""
Tests for Phase 3A: WeatherReport schema, social/citizen report adapters,
validation, normalization, and deterministic deduplication. Runs entirely
offline against the synthetic fixtures in data/phase3/fixtures/ -- no live
network or social-media/citizen-app access required or attempted.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from schemas.weather_report import WeatherReport, SOURCE_TYPES, EVENT_TYPES
from adapters.social_report_adapter import social_fixture_to_reports, infer_event_type_from_text
from adapters.citizen_report_adapter import citizen_fixture_to_reports, normalize_category
from ingestion.report_validators import validate_report, validate_reports
from ingestion.report_normalizer import normalize_report, normalize_reports, normalized_text_for_dedup
from ingestion.report_dedup import detect_duplicates, compute_duplicate_hash


def _make_report(**overrides) -> WeatherReport:
    defaults = dict(
        source_type="CITIZEN_REPORT",
        timestamp="2026-07-14T10:00:00Z",
        city="Jabalpur",
        state="Madhya Pradesh",
        latitude=23.25,
        longitude=80.0,
        text="Heavy rain reported in the area.",
        event_type="RAINFALL",
        raw_event_type="rain",
    )
    defaults.update(overrides)
    return WeatherReport(**defaults)


# ---------- 1. Schema sanity ----------
def test_weather_report_defaults_to_unverified():
    r = _make_report()
    assert r.verification_status == "UNVERIFIED"
    assert r.is_duplicate is False
    assert r.is_suspicious is False


def test_weather_report_separate_from_weather_record():
    from schemas.weather_record import WeatherRecord
    assert WeatherReport is not WeatherRecord
    r = _make_report()
    assert not hasattr(r, "wind_speed")  # confirms no accidental field bleed


# ---------- 2. Valid report passes validation cleanly ----------
def test_valid_report_passes_validation():
    r = validate_report(_make_report())
    assert r.verification_status == "UNVERIFIED"
    assert r.quality_flags == []


# ---------- 3. Missing timestamp ----------
def test_missing_timestamp_is_rejected():
    r = validate_report(_make_report(timestamp=None))
    assert r.verification_status == "REJECTED"
    assert "missing_timestamp" in r.quality_flags


# ---------- 4. Invalid latitude ----------
def test_invalid_latitude_is_rejected():
    r = validate_report(_make_report(latitude=128.5))
    assert r.verification_status == "REJECTED"
    assert "invalid_latitude" in r.quality_flags


# ---------- 5. Invalid longitude ----------
def test_invalid_longitude_is_rejected():
    r = validate_report(_make_report(longitude=-200.0))
    assert r.verification_status == "REJECTED"
    assert "invalid_longitude" in r.quality_flags


# ---------- 6. Invalid event category ----------
def test_invalid_event_category_is_flagged_suspicious():
    r = validate_report(_make_report(event_type="NOT_A_REAL_CATEGORY"))
    assert r.verification_status == "SUSPICIOUS"
    assert any(f.startswith("invalid_event_type") for f in r.quality_flags)


# ---------- 7. Malformed / near-empty text ----------
def test_empty_text_and_unknown_category_flagged_suspicious_not_dropped():
    r = validate_report(_make_report(text="", event_type="OTHER", raw_event_type="weird_xyz"))
    assert r.verification_status == "SUSPICIOUS"
    assert "empty_or_near_empty_text" in r.quality_flags
    # Not dropped -- still a real object with an id
    assert r.report_id is not None


def test_invalid_records_are_never_silently_discarded():
    reports = [_make_report(timestamp=None), _make_report(latitude=999)]
    validated = validate_reports(reports)
    assert len(validated) == 2  # both still present, just REJECTED
    assert all(r.verification_status == "REJECTED" for r in validated)


# ---------- 8. Social-media adapter/normalization ----------
def test_social_fixture_loads_and_produces_weather_reports():
    reports = social_fixture_to_reports()
    assert len(reports) > 0
    assert all(isinstance(r, WeatherReport) for r in reports)
    assert all(r.source_type == "SOCIAL_MEDIA" for r in reports)


def test_social_fixture_marks_synthetic_data_in_raw_payload():
    reports = social_fixture_to_reports()
    assert all("_synthetic_note" in r.raw_payload for r in reports)
    assert all("SYNTHETIC" in r.raw_payload["_synthetic_note"] for r in reports)


def test_social_author_handle_is_hashed_not_raw():
    reports = social_fixture_to_reports()
    r = reports[0]
    assert r.author_id_or_hash != r.raw_payload.get("author_handle")
    assert r.author_id_or_hash.startswith("sha256:")


def test_infer_event_type_from_text_flooding():
    assert infer_event_type_from_text("Massive waterlogging on the street") == "FLOODING"


def test_infer_event_type_from_text_unknown_defaults_to_other():
    assert infer_event_type_from_text("Just a regular sunny day, nothing unusual") == "OTHER"


# ---------- 9. Citizen-report adapter/normalization ----------
def test_citizen_fixture_loads_and_produces_weather_reports():
    reports = citizen_fixture_to_reports()
    assert len(reports) > 0
    assert all(isinstance(r, WeatherReport) for r in reports)
    assert all(r.source_type == "CITIZEN_REPORT" for r in reports)


def test_citizen_fixture_marks_synthetic_data_in_raw_payload():
    reports = citizen_fixture_to_reports()
    assert all("_synthetic_note" in r.raw_payload for r in reports)


def test_normalize_category_known_and_unknown():
    assert normalize_category("flooding") == "FLOODING"
    assert normalize_category("unknown_weird_category_xyz") == "OTHER"


# ---------- 10. Duplicate detection ----------
def test_exact_duplicate_detected():
    a = _make_report(text="Water logging on MG road due to heavy rain, cars stuck.",
                      timestamp="2026-07-14T10:35:00Z", latitude=23.1816, longitude=79.9865,
                      event_type="FLOODING")
    b = _make_report(text="Water logging on MG road due to heavy rain, cars stuck.",
                      timestamp="2026-07-14T10:36:00Z", latitude=23.1816, longitude=79.9865,
                      event_type="FLOODING")
    detect_duplicates([a, b])
    assert a.is_duplicate is False       # first seen = original
    assert b.is_duplicate is True
    assert a.duplicate_group_id == b.duplicate_group_id
    assert a.duplicate_hash == b.duplicate_hash


def test_different_reports_not_incorrectly_marked_duplicate():
    a = _make_report(text="Heavy rainfall near MG Road, Jabalpur", event_type="FLOODING",
                      timestamp="2026-07-14T10:32:00Z", latitude=23.1815, longitude=79.9864)
    b = _make_report(text="Dense fog near Delhi airport this morning", event_type="FOG",
                      timestamp="2026-07-15T05:10:00Z", latitude=28.5562, longitude=77.1)
    detect_duplicates([a, b])
    assert a.is_duplicate is False
    assert b.is_duplicate is False
    assert a.duplicate_group_id != b.duplicate_group_id


def test_near_duplicate_with_different_wording_is_not_caught_documented_limitation():
    """Documents a real, acknowledged limitation: deterministic exact-text
    dedup cannot catch paraphrased reports of the same event. This is
    intentional behavior for Phase 3A, not a bug -- Phase 3B (semantic
    similarity) is the recommended fix."""
    a = _make_report(text="Heavy rainfall and waterlogging near MG Road, Jabalpur right now!",
                      event_type="FLOODING", timestamp="2026-07-14T10:32:00Z",
                      latitude=23.1815, longitude=79.9864)
    b = _make_report(text="MG Road Jabalpur is completely flooded after today's downpour",
                      event_type="FLOODING", timestamp="2026-07-14T10:40:00Z",
                      latitude=23.1817, longitude=79.9863)
    detect_duplicates([a, b])
    # Different normalized text -> different hash -> NOT flagged as duplicates,
    # even though they describe the same real event.
    assert a.duplicate_hash != b.duplicate_hash
    assert b.is_duplicate is False


def test_duplicate_hash_is_deterministic():
    a = _make_report()
    h1 = compute_duplicate_hash(a)
    h2 = compute_duplicate_hash(a)
    assert h1 == h2


# ---------- 11. Verification defaults ----------
def test_new_reports_never_auto_verified():
    social = social_fixture_to_reports()
    citizen = citizen_fixture_to_reports()
    all_reports = validate_reports(social + citizen)
    assert all(r.verification_status != "VERIFIED" for r in all_reports)


# ---------- 12. Source reliability ----------
def test_source_reliability_assigned_by_normalization():
    r = normalize_report(_make_report(source_type="SOCIAL_MEDIA", source_reliability=None))
    assert r.source_reliability == 0.3  # DEFAULT_SOURCE_RELIABILITY["SOCIAL_MEDIA"]


def test_source_reliability_not_overwritten_if_already_set():
    r = normalize_report(_make_report(source_type="SOCIAL_MEDIA", source_reliability=0.99))
    assert r.source_reliability == 0.99


def test_source_reliability_documented_as_baseline_not_scientific():
    from schemas.weather_report import DEFAULT_SOURCE_RELIABILITY
    assert 0.0 <= DEFAULT_SOURCE_RELIABILITY["SOCIAL_MEDIA"] <= 1.0
    assert DEFAULT_SOURCE_RELIABILITY["API"] > DEFAULT_SOURCE_RELIABILITY["SOCIAL_MEDIA"]


# ---------- 13. Multiple locations / not hardcoded to Jabalpur ----------
def test_reports_support_multiple_indian_cities():
    social = social_fixture_to_reports()
    citizen = citizen_fixture_to_reports()
    cities = {r.city for r in social + citizen}
    assert len(cities) > 3  # Jabalpur, Delhi, Bhopal, Jaipur, Chennai, Nagpur, Patna, Lucknow, Kolkata
    assert "Jabalpur" in cities
    assert "Delhi" in cities or "Nagpur" in cities


# ---------- 14. Malformed input handled gracefully end-to-end ----------
def test_full_pipeline_handles_malformed_fixture_entries_without_crashing():
    social = social_fixture_to_reports()
    citizen = citizen_fixture_to_reports()
    all_reports = validate_reports(social + citizen)
    all_reports = normalize_reports(all_reports)
    all_reports = detect_duplicates(all_reports)
    assert len(all_reports) == len(social) + len(citizen)  # nothing dropped
    assert any(r.verification_status == "REJECTED" for r in all_reports)  # malformed entries caught


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
