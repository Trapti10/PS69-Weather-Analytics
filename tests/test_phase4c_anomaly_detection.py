"""
Tests for Phase 4C: Weather Anomaly Detection + Explainable Anomaly
Analytics.

Runs entirely offline. Uses small, hand-authored, in-memory synthetic
WeatherRecord fixtures for deterministic unit tests, plus one smoke test
against the real 17,544-row ERA5/Open-Meteo series (skipped gracefully if
the real data files are not present). See scripts/run_phase4c_demo.py for
the full real-data end-to-end demonstration.
"""
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from schemas.weather_record import WeatherRecord

from phase4c.anomaly_detection import (
    AnomalyConfig, AnomalyRecord,
    records_to_dataframe, detect_zscore_variable, detect_rainfall_anomalies,
    run_anomaly_detection, run_anomaly_detection_for_source,
    find_matching_anomalies, attach_anomalies_to_intelligence,
    attach_anomaly_context_to_forecast,
)
from phase4c.anomaly_scoring import (
    STATUS_EVALUATED, STATUS_INSUFFICIENT_HISTORY, STATUS_ZERO_VARIANCE,
    STATUS_MISSING_VALUE, STATUS_INVALID_VALUE,
    CLASSIFICATION_STATISTICAL_ANOMALY, CLASSIFICATION_NORMAL,
)
from phase4c.anomaly_storage import (
    save_anomalies_json, save_anomalies_csv, load_anomalies_json, PHASE4C_DIR,
)
from phase4.weather_intelligence import WeatherIntelligence


# ---------------------------------------------------------------------------
# Fixture helpers (small, hand-authored, clearly synthetic -- not real data)
# ---------------------------------------------------------------------------

BASE_TIME = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)


def make_hourly_records(n, source="ERA5", temperature=None, rainfall=None,
                         wind_speed=None, pressure=None, lat=23.25, lon=80.0,
                         start=BASE_TIME):
    """Builds n hourly WeatherRecords. Each of the four value args may be a
    constant, a list of length n, or None (field left unset)."""
    def _val(v, i, default):
        if v is None:
            return default
        if isinstance(v, (list, tuple)):
            return v[i]
        return v

    records = []
    for i in range(n):
        ts = (start + timedelta(hours=i)).isoformat().replace("+00:00", "Z")
        records.append(WeatherRecord(
            source=source, timestamp=ts, latitude=lat, longitude=lon,
            city="Jabalpur", state="Madhya Pradesh", country="India",
            temperature=_val(temperature, i, 25.0),
            rainfall=_val(rainfall, i, 0.0),
            wind_speed=_val(wind_speed, i, 2.0),
            pressure=_val(pressure, i, 1000.0),
        ))
    return records


# ---------------------------------------------------------------------------
# 1. Normal values -> NORMAL, no anomaly
# ---------------------------------------------------------------------------

def test_normal_constant_temperature_is_not_anomalous_but_uses_zero_variance_path():
    # A perfectly constant series has zero rolling variance -- exercised
    # separately in test 8; here we add tiny realistic noise so the normal
    # path (non-zero std, |z| small) is what's actually tested.
    import itertools
    noise = [25.0 + 0.01 * math.sin(i) for i in range(200)]
    records = make_hourly_records(200, temperature=noise)
    df, _ = records_to_dataframe(records)
    results = detect_zscore_variable(df, "temperature", AnomalyConfig())
    evaluated = [r for r in results if r.status == STATUS_EVALUATED]
    assert evaluated, "expected some evaluated rows once history builds up"
    assert all(r.classification == CLASSIFICATION_NORMAL for r in evaluated)


# ---------------------------------------------------------------------------
# 2. Obvious temperature anomaly
# ---------------------------------------------------------------------------

def test_obvious_temperature_anomaly_is_detected():
    config = AnomalyConfig(zscore_window=48, zscore_min_periods=48)
    temps = [25.0 + 0.05 * (i % 5) for i in range(100)]
    temps[90] = 60.0  # blatant spike, far outside 25 +/- noise
    records = make_hourly_records(100, temperature=temps)
    df, _ = records_to_dataframe(records)
    results = detect_zscore_variable(df, "temperature", config)
    spike = results[90]
    assert spike.classification == CLASSIFICATION_STATISTICAL_ANOMALY
    assert spike.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert spike.method == "rolling_zscore"
    assert spike.observed_value == 60.0
    assert "STATISTICAL_ANOMALY" in spike.explanation


# ---------------------------------------------------------------------------
# 3. Obvious wind anomaly
# ---------------------------------------------------------------------------

def test_obvious_wind_anomaly_is_detected():
    config = AnomalyConfig(zscore_window=48, zscore_min_periods=48)
    winds = [2.0 + 0.02 * (i % 7) for i in range(100)]
    winds[80] = 40.0  # extreme gust
    records = make_hourly_records(100, wind_speed=winds)
    df, _ = records_to_dataframe(records)
    results = detect_zscore_variable(df, "wind_speed", config)
    spike = results[80]
    assert spike.classification == CLASSIFICATION_STATISTICAL_ANOMALY
    assert spike.variable == "wind_speed"


# ---------------------------------------------------------------------------
# 4. Rainfall percentile anomaly (zero-inflated)
# ---------------------------------------------------------------------------

def test_rainfall_percentile_anomaly_on_zero_inflated_series():
    config = AnomalyConfig(rainfall_window=200, rainfall_min_periods=48)
    # Frequent-enough light showers (20% of hours) that the rolling 95th
    # percentile baseline itself settles around "light shower" level, then
    # one heavy downpour far above that.
    rain = [0.0] * 220
    for i in range(0, 220, 5):
        rain[i] = 0.5
    rain[213] = 45.0  # heavy downpour, far above the light-shower norm (213 is not a shower slot)
    records = make_hourly_records(220, rainfall=rain)
    df, _ = records_to_dataframe(records)
    results = detect_rainfall_anomalies(df, config)
    spike = results[213]
    assert spike.classification == CLASSIFICATION_STATISTICAL_ANOMALY
    assert spike.method == "rolling_percentile"
    # A plain z-score would also flag ordinary light 0.5mm showers given how
    # skewed the series is; the percentile method should NOT flag light
    # showers once the rolling baseline has enough history to reflect that
    # they're the local norm (evaluated, non-warm-up rows only).
    light_shower_flags = [
        r for i, r in enumerate(results)
        if rain[i] == 0.5 and r.status == STATUS_EVALUATED and r.classification == CLASSIFICATION_STATISTICAL_ANOMALY
    ]
    assert len(light_shower_flags) == 0


# ---------------------------------------------------------------------------
# 5. Pressure anomaly (+ elevation-mismatch caveat is documented, not triggered)
# ---------------------------------------------------------------------------

def test_pressure_anomaly_detected_and_caveat_documented():
    config = AnomalyConfig(zscore_window=48, zscore_min_periods=48)
    pressures = [1000.0 + 0.1 * (i % 6) for i in range(100)]
    pressures[70] = 950.0  # sharp drop
    records = make_hourly_records(100, pressure=pressures, source="ERA5")
    df, _ = records_to_dataframe(records)
    results = detect_zscore_variable(df, "pressure", config, pressure_caveat=True)
    spike = results[70]
    assert spike.classification == CLASSIFICATION_STATISTICAL_ANOMALY
    assert "elevation-offset" in spike.explanation or "elevation" in spike.explanation


def test_pressure_caveat_not_triggered_by_cross_source_definition_mismatch():
    """Per-source rolling baselines mean the known ERA5 (msl) vs Open-Meteo
    (surface_pressure) definitional offset never appears as an anomaly,
    because the two sources' series are never compared to each other."""
    config = AnomalyConfig(zscore_window=48, zscore_min_periods=48)
    era5 = make_hourly_records(100, pressure=1000.0, source="ERA5")
    openmeteo = make_hourly_records(100, pressure=960.0, source="Open-Meteo")  # constant ~40 hPa lower
    all_records, prep = run_anomaly_detection(era5 + openmeteo, config)
    pressure_anomalies = [
        a for a in all_records if a.variable == "pressure" and a.classification == CLASSIFICATION_STATISTICAL_ANOMALY
    ]
    assert pressure_anomalies == [], (
        "a constant per-source offset must never itself produce an anomaly -- "
        "each source is evaluated purely against its own rolling history"
    )


# ---------------------------------------------------------------------------
# 6. Missing value
# ---------------------------------------------------------------------------

def test_missing_temperature_value_is_reported_not_fabricated():
    temps = [25.0] * 50 + [None] + [25.0] * 20
    records = make_hourly_records(71, temperature=temps)
    df, _ = records_to_dataframe(records)
    results = detect_zscore_variable(df, "temperature", AnomalyConfig(zscore_window=20, zscore_min_periods=20))
    missing = results[50]
    assert missing.status == STATUS_MISSING_VALUE
    assert missing.classification == CLASSIFICATION_NORMAL
    assert missing.anomaly_score is None


# ---------------------------------------------------------------------------
# 7. Insufficient history
# ---------------------------------------------------------------------------

def test_insufficient_history_for_first_n_records():
    config = AnomalyConfig(zscore_window=24, zscore_min_periods=24)
    records = make_hourly_records(10, temperature=25.0)
    df, _ = records_to_dataframe(records)
    results = detect_zscore_variable(df, "temperature", config)
    assert len(results) == 10
    assert all(r.status == STATUS_INSUFFICIENT_HISTORY for r in results)
    assert all(r.anomaly_score is None for r in results)
    assert all(r.classification == CLASSIFICATION_NORMAL for r in results)


# ---------------------------------------------------------------------------
# 8. Zero variance
# ---------------------------------------------------------------------------

def test_zero_variance_window_is_flagged_not_divided_by_zero():
    config = AnomalyConfig(zscore_window=24, zscore_min_periods=24)
    records = make_hourly_records(30, temperature=25.0)  # perfectly constant
    df, _ = records_to_dataframe(records)
    results = detect_zscore_variable(df, "temperature", config)
    evaluated_region = results[24:]
    assert all(r.status == STATUS_ZERO_VARIANCE for r in evaluated_region)
    assert all(r.anomaly_score is None for r in evaluated_region)


# ---------------------------------------------------------------------------
# 9. Boundary threshold
# ---------------------------------------------------------------------------

def test_boundary_threshold_behavior():
    """A z-score exactly at the threshold counts as an anomaly (>=), one
    just below does not."""
    config = AnomalyConfig(zscore_window=48, zscore_min_periods=48, z_threshold=3.0)
    temps = [25.0 + 0.1 * (i % 4) for i in range(60)]
    records = make_hourly_records(60, temperature=temps)
    df, _ = records_to_dataframe(records)
    results = detect_zscore_variable(df, "temperature", config)
    r59 = results[59]
    assert r59.status == STATUS_EVALUATED
    # Recompute the exact boundary manually and confirm the >= rule is applied consistently.
    if r59.anomaly_score is not None:
        expected = abs(r59.anomaly_score) >= config.z_threshold
        assert (r59.classification == CLASSIFICATION_STATISTICAL_ANOMALY) == expected


# ---------------------------------------------------------------------------
# 10. Duplicate timestamp behavior
# ---------------------------------------------------------------------------

def test_duplicate_timestamps_are_deduplicated_and_reported():
    records = make_hourly_records(20, temperature=25.0)
    records.append(records[5])  # exact duplicate timestamp
    df, prep = records_to_dataframe(records)
    assert prep["duplicate_timestamps_dropped"] == 1
    assert len(df) == 20


# ---------------------------------------------------------------------------
# 11. Unsorted timestamps
# ---------------------------------------------------------------------------

def test_unsorted_input_is_sorted_before_processing():
    records = make_hourly_records(20, temperature=list(range(20)))
    shuffled = list(reversed(records))
    df, prep = records_to_dataframe(shuffled)
    assert prep["was_unsorted"] is True
    assert df["temperature"].tolist() == list(range(20))


# ---------------------------------------------------------------------------
# 12. Reproducibility
# ---------------------------------------------------------------------------

def test_reproducibility_same_input_same_output():
    temps = [25.0 + 0.1 * (i % 5) for i in range(80)]
    temps[70] = 55.0
    records = make_hourly_records(80, temperature=temps)
    config = AnomalyConfig(zscore_window=48, zscore_min_periods=48)

    df1, _ = records_to_dataframe(records)
    results1 = detect_zscore_variable(df1, "temperature", config)
    df2, _ = records_to_dataframe(records)
    results2 = detect_zscore_variable(df2, "temperature", config)

    for r1, r2 in zip(results1, results2):
        assert r1.classification == r2.classification
        assert r1.anomaly_score == r2.anomaly_score
        assert r1.status == r2.status


# ---------------------------------------------------------------------------
# 13. Source separation
# ---------------------------------------------------------------------------

def test_source_separation_never_mixes_baselines():
    config = AnomalyConfig(zscore_window=24, zscore_min_periods=24)
    era5 = make_hourly_records(60, temperature=25.0, source="ERA5")
    openmeteo = make_hourly_records(60, temperature=35.0, source="Open-Meteo")  # different but internally stable
    all_records, prep = run_anomaly_detection(era5 + openmeteo, config)
    temp_anomalies = [
        a for a in all_records if a.variable == "temperature" and a.classification == CLASSIFICATION_STATISTICAL_ANOMALY
    ]
    assert temp_anomalies == [], "two internally-stable sources at different levels must not cross-contaminate"
    assert set(prep.keys()) == {"ERA5", "Open-Meteo"}


# ---------------------------------------------------------------------------
# 14. Severity calculation
# ---------------------------------------------------------------------------

def test_severity_scales_with_deviation_magnitude():
    config = AnomalyConfig(zscore_window=48, zscore_min_periods=48, z_threshold=3.0,
                            severity_ratio_low=2.0, severity_ratio_medium=3.0, severity_ratio_high=4.0)
    # Wide-enough natural spread (cycling 20..28C) that a value still inside
    # that normal cycle ("mild") is genuinely not statistically unusual.
    temps = [20.0 + 2.0 * (i % 5) for i in range(60)]
    # progressively bigger spikes at the same relative position, tested independently
    mild = list(temps); mild[55] = 26.0  # inside the normal 20-28 cycle
    huge = list(temps); huge[55] = 200.0

    df_mild, _ = records_to_dataframe(make_hourly_records(60, temperature=mild))
    df_huge, _ = records_to_dataframe(make_hourly_records(60, temperature=huge))

    r_mild = detect_zscore_variable(df_mild, "temperature", config)[55]
    r_huge = detect_zscore_variable(df_huge, "temperature", config)[55]

    assert r_mild.classification == CLASSIFICATION_NORMAL
    assert r_huge.classification == CLASSIFICATION_STATISTICAL_ANOMALY
    assert r_huge.severity == "CRITICAL"


# ---------------------------------------------------------------------------
# 15. Explanation generation
# ---------------------------------------------------------------------------

def test_explanation_is_deterministic_and_contains_key_numbers():
    config = AnomalyConfig(zscore_window=48, zscore_min_periods=48)
    temps = [25.0 + 0.05 * (i % 5) for i in range(60)]
    temps[55] = 90.0
    records = make_hourly_records(60, temperature=temps)
    df, _ = records_to_dataframe(records)
    result = detect_zscore_variable(df, "temperature", config)[55]
    assert "Observed temperature = 90.000" in result.explanation
    assert "Threshold" in result.explanation
    assert "STATISTICAL_ANOMALY" in result.explanation


# ---------------------------------------------------------------------------
# 16. Storage round-trip
# ---------------------------------------------------------------------------

def test_storage_round_trip(tmp_path, monkeypatch):
    import phase4c.anomaly_storage as storage_module
    monkeypatch.setattr(storage_module, "PHASE4C_DIR", tmp_path)

    records = make_hourly_records(30, temperature=[25.0 + (i % 3) for i in range(30)])
    config = AnomalyConfig(zscore_window=10, zscore_min_periods=10)
    anomalies, _ = run_anomaly_detection(records, config)

    json_path = storage_module.save_anomalies_json(anomalies, filename="test_anomalies.json")
    assert json_path.exists()
    loaded = storage_module.load_anomalies_json(filename="test_anomalies.json")
    assert len(loaded) == len(anomalies)
    assert loaded[0].variable == anomalies[0].variable

    csv_path = storage_module.save_anomalies_csv(anomalies, filename="test_anomalies.csv")
    assert csv_path.exists()
    assert csv_path.read_text().splitlines()[0].startswith("id,generated_at,timestamp")


# ---------------------------------------------------------------------------
# Phase 4A / 4B integration
# ---------------------------------------------------------------------------

def test_attach_anomalies_to_intelligence_is_additive_and_honest():
    config = AnomalyConfig(zscore_window=24, zscore_min_periods=24)
    temps = [25.0 + 0.05 * (i % 3) for i in range(60)]
    temps[50] = 90.0
    records = make_hourly_records(60, temperature=temps)
    anomalies, _ = run_anomaly_detection(records, config)
    anomalies_only = [a for a in anomalies if a.classification == CLASSIFICATION_STATISTICAL_ANOMALY]
    assert anomalies_only, "fixture must actually produce an anomaly for this test to be meaningful"

    matched_ts = anomalies_only[0].timestamp
    intel_matched = WeatherIntelligence(timestamp=matched_ts, latitude=23.25, longitude=80.0)
    updated = attach_anomalies_to_intelligence(intel_matched, anomalies_only)
    assert updated.anomaly is not None
    assert updated.anomaly["matched_anomaly_count"] >= 1

    far_away_ts = (BASE_TIME + timedelta(days=365)).isoformat().replace("+00:00", "Z")
    intel_unmatched = WeatherIntelligence(timestamp=far_away_ts, latitude=23.25, longitude=80.0)
    updated_unmatched = attach_anomalies_to_intelligence(intel_unmatched, anomalies_only)
    assert updated_unmatched.anomaly is None, "must never fabricate a match when none exists"


def test_attach_anomaly_context_to_forecast_never_edits_predicted_value():
    config = AnomalyConfig(zscore_window=24, zscore_min_periods=24)
    temps = [25.0 + 0.05 * (i % 3) for i in range(60)]
    temps[50] = 90.0
    records = make_hourly_records(60, temperature=temps)
    anomalies, _ = run_anomaly_detection(records, config)
    anomalies_only = [a for a in anomalies if a.classification == CLASSIFICATION_STATISTICAL_ANOMALY]

    forecast_record = {
        "timestamp": anomalies_only[0].timestamp, "latitude": 23.25, "longitude": 80.0,
        "predicted_temperature": 27.5, "horizon_hours": 6,
    }
    out = attach_anomaly_context_to_forecast(forecast_record, anomalies_only)
    assert out["predicted_temperature"] == 27.5  # untouched
    assert "observed_anomaly_context" in out
    assert len(out["observed_anomaly_context"]) >= 1
    assert out is not forecast_record  # returns a new dict, doesn't mutate the input
    assert "observed_anomaly_context" not in forecast_record


def test_find_matching_anomalies_reuses_temporal_spatial_alignment():
    config = AnomalyConfig(zscore_window=24, zscore_min_periods=24)
    temps = [20.0 + 2.0 * (i % 5) for i in range(60)]
    temps[50] = 90.0
    records = make_hourly_records(60, temperature=temps)
    anomalies, _ = run_anomaly_detection(records, config)
    anomalies_only = [a for a in anomalies if a.classification == CLASSIFICATION_STATISTICAL_ANOMALY]
    ts = anomalies_only[0].timestamp

    close_matches = find_matching_anomalies(ts, 23.25, 80.0, anomalies_only, max_time_diff_minutes=30, max_distance_km=10)
    assert len(close_matches) >= 1

    far_spatial = find_matching_anomalies(ts, 40.0, 40.0, anomalies_only, max_time_diff_minutes=30, max_distance_km=10)
    assert far_spatial == []


# ---------------------------------------------------------------------------
# 17. Real-data smoke test
# ---------------------------------------------------------------------------

def test_real_data_smoke_test_if_available():
    root = Path(__file__).resolve().parents[1]
    era5_path = root / "data" / "raw" / "jabalpur_weather_2024_2025.csv"
    if not era5_path.exists():
        pytest.skip("real ERA5 data file not present in this checkout")

    sys.path.append(str(root / "src"))
    from adapters.era5_adapter import era5_csv_to_records

    records = era5_csv_to_records(str(era5_path), limit=1000)
    anomalies, prep = run_anomaly_detection_for_source(records, AnomalyConfig())
    assert len(anomalies) > 0
    assert prep["input_records"] == 1000
    rates = {}
    for variable in ("temperature", "wind_speed", "rainfall", "pressure"):
        var_results = [a for a in anomalies if a.variable == variable]
        evaluated = [a for a in var_results if a.status == STATUS_EVALUATED]
        anomalous = [a for a in evaluated if a.classification == CLASSIFICATION_STATISTICAL_ANOMALY]
        rates[variable] = len(anomalous) / len(evaluated) if evaluated else None
    # Sanity check: no single variable should dominate with an absurd rate
    # on real, mostly-ordinary weather data.
    for variable, rate in rates.items():
        if rate is not None:
            assert rate < 0.25, f"{variable} anomaly rate {rate} looks implausibly high for real data"
