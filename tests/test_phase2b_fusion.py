"""
Tests for Phase 2B: ERA5 adapter, temporal/spatial alignment, source
comparison, and fusion. Runs entirely offline (ERA5 CSV + IMD fixtures) --
no live IMD access required.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from adapters.era5_adapter import era5_csv_to_records, load_era5_raw
from ingestion.imd_client import IMDClient
from ingestion.validators import process_raw_records
from schemas.weather_record import WeatherRecord
from fusion.temporal_alignment import check_temporal_match
from fusion.spatial_alignment import check_spatial_match, haversine_km
from fusion.source_comparison import compare_variable, compare_records
from fusion.fusion_engine import fuse_pair

ERA5_PATH = str(Path(__file__).resolve().parents[1] / "data" / "raw" / "jabalpur_weather_2024_2025.csv")


# ---------- 1. ERA5 loading ----------
def test_era5_raw_loads():
    df = load_era5_raw(ERA5_PATH)
    assert len(df) > 0
    assert "t2m" in df.columns


# ---------- 2. ERA5 unit conversion ----------
def test_era5_unit_conversion_correctness():
    records = era5_csv_to_records(ERA5_PATH, limit=1)
    r = records[0]
    # Known Phase-1 fact: first row has t2m in Kelvin; converted temp must be plausible Celsius
    assert -10 <= r.temperature <= 55
    assert 870 <= r.pressure <= 1085
    assert r.rainfall >= 0


def test_era5_adapter_produces_weather_record():
    records = era5_csv_to_records(ERA5_PATH, limit=5)
    assert len(records) == 5
    assert all(isinstance(r, WeatherRecord) for r in records)
    assert all(r.source == "ERA5" for r in records)


# ---------- 3. WeatherRecord creation (shared schema) ----------
def test_era5_and_imd_produce_same_schema_type():
    era5_records = era5_csv_to_records(ERA5_PATH, limit=1)
    client = IMDClient(use_fixtures=True)
    raw_imd = client.get_current_weather("42182")
    imd_records = process_raw_records(raw_imd, endpoint="current_wx")
    assert type(era5_records[0]) == type(imd_records[0]) == WeatherRecord


# ---------- 4. Temporal matching ----------
def test_temporal_match_within_tolerance():
    result = check_temporal_match("2024-01-01T06:00:00Z", "2024-01-01T06:30:00Z", max_time_diff_minutes=60)
    assert result.is_match
    assert result.flag == "TEMPORAL_MATCH"
    assert result.time_difference_minutes == 30.0


def test_temporal_mismatch_outside_tolerance():
    result = check_temporal_match("2024-01-01T06:00:00Z", "2024-01-02T06:00:00Z", max_time_diff_minutes=60)
    assert not result.is_match
    assert result.flag == "TEMPORAL_MISMATCH"


def test_temporal_unknown_on_missing_timestamp():
    result = check_temporal_match(None, "2024-01-01T06:00:00Z")
    assert result.flag == "TEMPORAL_UNKNOWN"


# ---------- 5/6. Spatial matching + Haversine ----------
def test_haversine_known_distance():
    # Delhi to Mumbai is approximately 1150-1160 km
    d = haversine_km(28.6139, 77.2090, 19.0760, 72.8777)
    assert 1100 < d < 1200


def test_haversine_zero_distance_same_point():
    d = haversine_km(23.25, 80.0, 23.25, 80.0)
    assert d == 0.0


def test_spatial_match_within_threshold():
    result = check_spatial_match(23.25, 80.0, 23.18, 79.95, max_distance_km=25)
    assert result.is_match
    assert result.flag == "SPATIAL_MATCH"


def test_spatial_mismatch_outside_threshold():
    result = check_spatial_match(23.25, 80.0, 28.6139, 77.2090, max_distance_km=25)  # Jabalpur vs Delhi
    assert not result.is_match
    assert result.flag == "SPATIAL_MISMATCH"


def test_spatial_unknown_on_missing_coords():
    result = check_spatial_match(None, None, 23.18, 79.95)
    assert result.flag == "SPATIAL_UNKNOWN"


# ---------- 7. Source comparison ----------
def test_compare_variable_high_agreement():
    c = compare_variable("temperature", 25.0, 25.5)
    assert c.agreement_flag == "SOURCE_AGREEMENT_HIGH"


def test_compare_variable_disagreement():
    c = compare_variable("temperature", 20.0, 35.0)
    assert c.agreement_flag == "SOURCE_DISAGREEMENT"


def test_compare_variable_unavailable_when_missing():
    c = compare_variable("humidity", None, 50.0)
    assert c.agreement_flag == "SOURCE_COMPARISON_UNAVAILABLE"


def test_rainfall_uses_absolute_not_percent():
    # 0.0 vs 0.2mm would be "infinite" percent difference but is not meaningful
    c = compare_variable("rainfall", 0.0, 0.2)
    assert c.percent_difference is None
    assert c.agreement_flag == "SOURCE_AGREEMENT_HIGH"


# ---------- 8/9/10. Disagreement detection, confidence, fusion output ----------
def _make_record(source, timestamp, lat, lon, temperature, pressure, rainfall, wind_speed):
    return WeatherRecord(source=source, timestamp=timestamp, latitude=lat, longitude=lon,
                          temperature=temperature, pressure=pressure, rainfall=rainfall,
                          wind_speed=wind_speed, verification_status="validated", confidence_score=0.9)


def test_fusion_matched_high_agreement_produces_fused_value():
    a = _make_record("ERA5", "2024-01-01T06:00:00Z", 23.25, 80.0, 25.0, 1010.0, 0.0, 2.0)
    b = _make_record("IMD", "2024-01-01T06:15:00Z", 23.20, 79.98, 25.3, 1010.5, 0.0, 2.1)
    result = fuse_pair(a, b, max_time_diff_minutes=60, max_distance_km=25)
    assert result["match_status"] == "MATCHED"
    assert result["fusion"]["temperature"] is not None
    assert result["fusion"]["confidence_score"] > 0.8


def test_fusion_disagreement_does_not_average():
    a_agree = _make_record("ERA5", "2024-01-01T06:00:00Z", 23.25, 80.0, 25.0, 1010.0, 0.0, 2.0)
    b_agree = _make_record("IMD", "2024-01-01T06:15:00Z", 23.20, 79.98, 25.3, 1010.5, 0.0, 2.1)
    result_agree = fuse_pair(a_agree, b_agree, max_time_diff_minutes=60, max_distance_km=25)

    a_dis = _make_record("ERA5", "2024-01-01T06:00:00Z", 23.25, 80.0, 20.0, 1010.0, 0.0, 2.0)
    b_dis = _make_record("IMD", "2024-01-01T06:15:00Z", 23.20, 79.98, 35.0, 1010.5, 0.0, 2.1)
    result_dis = fuse_pair(a_dis, b_dis, max_time_diff_minutes=60, max_distance_km=25)

    assert result_dis["comparison"]["temperature"]["agreement_flag"] == "SOURCE_DISAGREEMENT"
    assert result_dis["fusion"]["temperature"] is None  # NOT averaged, unlike the agreeing case
    assert result_agree["fusion"]["temperature"] is not None
    # A disagreement on one variable must pull overall confidence below the
    # all-high-agreement case -- this is the relative behavior that matters,
    # not a specific absolute number.
    assert result_dis["fusion"]["confidence_score"] < result_agree["fusion"]["confidence_score"]


def test_fusion_not_attempted_when_not_matched():
    a = _make_record("ERA5", "2024-01-01T06:00:00Z", 23.25, 80.0, 25.0, 1010.0, 0.0, 2.0)
    b = _make_record("IMD", "2024-06-01T06:00:00Z", 23.25, 80.0, 25.0, 1010.0, 0.0, 2.0)  # months apart
    result = fuse_pair(a, b, max_time_diff_minutes=60, max_distance_km=25)
    assert result["match_status"] == "NOT_MATCHED"
    assert result["comparison"] == {}
    assert result["fusion"]["confidence_score"] is None


def test_fusion_preserves_both_raw_source_values():
    a = _make_record("ERA5", "2024-01-01T06:00:00Z", 23.25, 80.0, 20.0, 1010.0, 0.0, 2.0)
    b = _make_record("IMD", "2024-01-01T06:15:00Z", 23.20, 79.98, 35.0, 1010.5, 0.0, 2.1)
    result = fuse_pair(a, b, max_time_diff_minutes=60, max_distance_km=25)
    assert result["sources"]["ERA5"]["temperature"] == 20.0
    assert result["sources"]["IMD"]["temperature"] == 35.0  # both preserved, neither overwritten


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
