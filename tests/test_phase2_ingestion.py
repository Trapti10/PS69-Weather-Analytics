"""
Tests for Phase 2 ingestion. Runs entirely offline using fixtures — does
not require live IMD access (see imd_client.py for why).
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from ingestion.imd_client import IMDClient
from ingestion.validators import process_raw_records, validate_record
from schemas.weather_record import WeatherRecord


def test_fixture_current_wx_loads():
    client = IMDClient(use_fixtures=True)
    raw = client.get_current_weather(station_id="42182")
    assert isinstance(raw, list)
    assert len(raw) > 0
    assert "Station Id" in raw[0]


def test_fixture_aws_data_loads():
    client = IMDClient(use_fixtures=True)
    raw = client.get_aws_data(call_sign="NDL")
    assert isinstance(raw, list)
    assert raw[0]["STATE"] == "DELHI"


def test_current_wx_maps_to_weather_record():
    client = IMDClient(use_fixtures=True)
    raw = client.get_current_weather(station_id="42182")
    records = process_raw_records(raw, endpoint="current_wx")
    assert len(records) == 1
    r = records[0]
    assert isinstance(r, WeatherRecord)
    assert r.source == "IMD"
    assert r.station_id == "42182"
    assert r.temperature == 29.4
    assert r.verification_status in ("validated", "flagged")


def test_aws_data_maps_to_weather_record():
    client = IMDClient(use_fixtures=True)
    raw = client.get_aws_data(call_sign="NDL")
    records = process_raw_records(raw, endpoint="aws_data")
    assert len(records) == 1
    r = records[0]
    assert r.source == "IMD"
    assert r.state == "DELHI"
    assert r.latitude == 28.5885
    # 40.8C is within plausible range, so this should validate cleanly
    assert r.verification_status == "validated"
    assert r.quality_flags == []


def test_out_of_range_temperature_is_flagged():
    r = WeatherRecord(source="IMD", temperature=95.0, timestamp="2026-01-01T00:00:00Z")
    r = validate_record(r)
    assert "temperature_out_of_range" in r.quality_flags
    assert r.verification_status == "flagged"
    assert r.confidence_score < 0.9


def test_missing_timestamp_is_flagged():
    r = WeatherRecord(source="IMD", temperature=25.0, city="Test City")
    r = validate_record(r)
    assert "missing_timestamp" in r.quality_flags


def test_wind_speed_unit_conversion_kmph_to_ms():
    client = IMDClient(use_fixtures=True)
    raw = client.get_current_weather(station_id="42182")
    records = process_raw_records(raw, endpoint="current_wx")
    # fixture has Wind Speed = 8 KMPH -> should become ~2.222 m/s
    assert abs(records[0].wind_speed - 2.222) < 0.01


if __name__ == "__main__":
    import traceback
    tests = [
        test_fixture_current_wx_loads,
        test_fixture_aws_data_loads,
        test_current_wx_maps_to_weather_record,
        test_aws_data_maps_to_weather_record,
        test_out_of_range_temperature_is_flagged,
        test_missing_timestamp_is_flagged,
        test_wind_speed_unit_conversion_kmph_to_ms,
    ]
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
