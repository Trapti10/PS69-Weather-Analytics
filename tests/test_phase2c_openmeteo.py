"""
Tests for Phase 2C: Open-Meteo adapter, and real ERA5+Open-Meteo cross-model
alignment/comparison/fusion. Runs entirely offline against the real,
user-downloaded files already on disk:
    data/raw/jabalpur_weather_2024_2025.csv        (Phase 1, ERA5)
    data/raw/jabalpur_openmeteo_2024_2025.json     (Phase 2C, Open-Meteo)
No live network access is required or attempted.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from adapters.era5_adapter import era5_csv_to_records
from adapters.openmeteo_adapter import openmeteo_json_to_records, load_openmeteo_raw
from schemas.weather_record import WeatherRecord
from fusion.temporal_alignment import check_temporal_match
from fusion.spatial_alignment import check_spatial_match, haversine_km
from fusion.source_comparison import compare_variable
from fusion.fusion_engine import fuse_pair

ERA5_PATH = str(Path(__file__).resolve().parents[1] / "data" / "raw" / "jabalpur_weather_2024_2025.csv")
OPENMETEO_PATH = str(Path(__file__).resolve().parents[1] / "data" / "raw" / "jabalpur_openmeteo_2024_2025.json")


# ---------- 1. Open-Meteo raw loading ----------
def test_openmeteo_raw_loads_real_file():
    payload = load_openmeteo_raw(OPENMETEO_PATH)
    assert "hourly" in payload
    assert "time" in payload["hourly"]
    assert len(payload["hourly"]["time"]) > 0


def test_openmeteo_raw_is_real_two_year_hourly_series():
    payload = load_openmeteo_raw(OPENMETEO_PATH)
    # Real file: 2024-01-01 to 2025-12-31 hourly = 17,544 hours (2024 is a leap year)
    assert len(payload["hourly"]["time"]) == 17544
    assert payload["hourly"]["time"][0] == "2024-01-01T00:00"
    assert payload["hourly"]["time"][-1] == "2025-12-31T23:00"


# ---------- 2. Adapter produces standardized WeatherRecords ----------
def test_openmeteo_adapter_produces_weather_record():
    records = openmeteo_json_to_records(OPENMETEO_PATH, limit=5)
    assert len(records) == 5
    assert all(isinstance(r, WeatherRecord) for r in records)
    assert all(r.source == "Open-Meteo" for r in records)


def test_openmeteo_timestamp_is_utc_iso():
    records = openmeteo_json_to_records(OPENMETEO_PATH, limit=1)
    r = records[0]
    assert r.timestamp == "2024-01-01T00:00:00Z"


def test_openmeteo_units_within_plausible_range():
    records = openmeteo_json_to_records(OPENMETEO_PATH, limit=100)
    for r in records:
        if r.temperature is not None:
            assert -10 <= r.temperature <= 55
        if r.humidity is not None:
            assert 0 <= r.humidity <= 100
        if r.rainfall is not None:
            assert r.rainfall >= 0


def test_openmeteo_wind_gust_preserved_in_raw_payload():
    # Schema has no gust field (same as ERA5's fg10) -- must be in raw_payload, not dropped
    records = openmeteo_json_to_records(OPENMETEO_PATH, limit=5)
    assert all("wind_gust" in r.raw_payload for r in records)


def test_openmeteo_wind_direction_honestly_none():
    # wind_direction_10m was not requested in the real pull -- must be None, never guessed
    records = openmeteo_json_to_records(OPENMETEO_PATH, limit=5)
    assert all(r.wind_direction is None for r in records)


def test_openmeteo_and_era5_produce_same_schema_type():
    era5_records = era5_csv_to_records(ERA5_PATH, limit=1)
    om_records = openmeteo_json_to_records(OPENMETEO_PATH, limit=1)
    assert type(era5_records[0]) == type(om_records[0]) == WeatherRecord


def test_openmeteo_malformed_file_raises_not_fabricates(tmp_path):
    import json
    bad_file = tmp_path / "not_openmeteo.json"
    bad_file.write_text(json.dumps({"unexpected": "shape"}))
    try:
        openmeteo_json_to_records(str(bad_file))
        assert False, "should have raised ValueError"
    except ValueError:
        pass


# ---------- 3. Real overlap: ERA5 and Open-Meteo share the same real period ----------
def test_era5_and_openmeteo_have_real_overlapping_timestamps_no_shifting():
    era5_records = era5_csv_to_records(ERA5_PATH, limit=50)
    om_records = openmeteo_json_to_records(OPENMETEO_PATH, limit=50)
    # These are REAL timestamps from two independently-fetched real files --
    # if they line up, it's because both cover the same real period, not
    # because either was synthetically shifted (neither adapter touches
    # timestamps beyond parsing/formatting).
    matching = sum(1 for a, b in zip(era5_records, om_records) if a.timestamp == b.timestamp)
    assert matching == 50


def test_era5_and_openmeteo_grid_points_are_spatially_close():
    era5_records = era5_csv_to_records(ERA5_PATH, limit=1)
    om_records = openmeteo_json_to_records(OPENMETEO_PATH, limit=1)
    result = check_spatial_match(
        era5_records[0].latitude, era5_records[0].longitude,
        om_records[0].latitude, om_records[0].longitude,
        max_distance_km=25,
    )
    assert result.is_match
    assert result.flag == "SPATIAL_MATCH"
    assert result.distance_km < 5  # real grid points are ~1.8km apart


def test_era5_and_openmeteo_temporal_match_on_real_shared_hour():
    era5_records = era5_csv_to_records(ERA5_PATH, limit=1)
    om_records = openmeteo_json_to_records(OPENMETEO_PATH, limit=1)
    result = check_temporal_match(era5_records[0].timestamp, om_records[0].timestamp, max_time_diff_minutes=60)
    assert result.is_match
    assert result.flag == "TEMPORAL_MATCH"
    assert result.time_difference_minutes == 0.0  # exact same real hour, no shifting


# ---------- 4. fuse_pair works generically for a THIRD source (per Phase 2B's design claim) ----------
def test_fuse_pair_generalizes_to_era5_openmeteo_without_modification():
    era5_records = era5_csv_to_records(ERA5_PATH, limit=1)
    om_records = openmeteo_json_to_records(OPENMETEO_PATH, limit=1)
    result = fuse_pair(era5_records[0], om_records[0], label_a="ERA5", label_b="Open-Meteo",
                        max_time_diff_minutes=60, max_distance_km=25)
    assert result["match_status"] == "MATCHED"
    assert "ERA5" in result["sources"]
    assert "Open-Meteo" in result["sources"]
    assert "temperature" in result["comparison"]


def test_real_temperature_agreement_on_first_real_pair():
    # Documented, real, reproducible finding (not asserting a specific
    # meteorological truth -- just that the pipeline classifies it correctly
    # given the real values 13.055C vs 12.9C).
    era5_records = era5_csv_to_records(ERA5_PATH, limit=1)
    om_records = openmeteo_json_to_records(OPENMETEO_PATH, limit=1)
    result = fuse_pair(era5_records[0], om_records[0], label_a="ERA5", label_b="Open-Meteo")
    assert result["comparison"]["temperature"]["agreement_flag"] == "SOURCE_AGREEMENT_HIGH"
    assert result["fusion"]["temperature"] is not None


# ---------- 5. Documented pressure caveat: surface pressure vs MSL is a real, large, systematic offset ----------
def test_pressure_caveat_is_real_and_large():
    """This is a documented LIMITATION, not a bug: Open-Meteo's
    surface_pressure (this pull's variable) differs from ERA5's
    mean-sea-level pressure by Jabalpur's real elevation (~390m), a
    systematic ~35-45 hPa gap that is NOT a genuine weather disagreement.
    The test asserts the gap is real and large, so this caveat cannot be
    silently forgotten in Phase 3."""
    era5_records = era5_csv_to_records(ERA5_PATH, limit=1)
    om_records = openmeteo_json_to_records(OPENMETEO_PATH, limit=1)
    diff = abs(era5_records[0].pressure - om_records[0].pressure)
    assert diff > 30  # real, large, elevation-driven -- not a rounding artifact


def test_pressure_percent_threshold_masks_the_elevation_offset():
    """Documented, real methodological finding: because pressure's baseline
    magnitude (~1000 hPa) is large, a 46 hPa absolute gap is only ~4.5%
    relative difference -- under the existing 5% HIGH-agreement threshold.
    This mirrors why rainfall already needed a special absolute-mm
    threshold (source_comparison.py docstring); pressure has the same
    problem but is NOT special-cased in Phase 2B. Documenting this
    honestly rather than silently patching source_comparison.py, per the
    instruction not to modify Phase 2B files."""
    c = compare_variable("pressure", 1016.668, 970.2)  # real values from first pair
    assert c.agreement_flag == "SOURCE_AGREEMENT_HIGH"  # counterintuitive but real behavior
    assert c.absolute_difference > 40


# ---------- 6. Disagreement handling still preserves both raw values (Phase 2B guarantee, reused) ----------
def test_wind_speed_disagreement_preserves_both_raw_values():
    era5_records = era5_csv_to_records(ERA5_PATH, limit=1)
    om_records = openmeteo_json_to_records(OPENMETEO_PATH, limit=1)
    result = fuse_pair(era5_records[0], om_records[0], label_a="ERA5", label_b="Open-Meteo")
    assert result["sources"]["ERA5"]["wind_speed"] == era5_records[0].wind_speed
    assert result["sources"]["Open-Meteo"]["wind_speed"] == om_records[0].wind_speed


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            if "tmp_path" in t.__code__.co_varnames[:t.__code__.co_argcount]:
                import tempfile
                with tempfile.TemporaryDirectory() as d:
                    t(Path(d))
            else:
                t()
            print(f"PASS: {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL: {t.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
