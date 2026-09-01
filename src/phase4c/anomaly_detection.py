"""
Phase 4C -- Weather Anomaly Detection + Explainable Anomaly Analytics.

Turns normalized WeatherRecord observations (Phase 1's schema, reused
unmodified -- src/schemas/weather_record.py) into explainable
`AnomalyRecord`s for four variables: temperature, wind_speed, rainfall,
pressure.

*** WHAT "ANOMALY" MEANS HERE, EXPLICITLY ***
An anomaly produced by this module is a STATISTICAL_ANOMALY: an observation
that is unusual relative to that same source's own recent rolling history,
by a documented, configurable, deterministic rule. It is NEVER:
    - a disaster
    - an emergency
    - a confirmed extreme weather event (heatwave/cyclone/flood/tornado/etc.)
    - a warning
    - a truth judgment
`AnomalyRecord.classification` is always the literal string
"STATISTICAL_ANOMALY" (or "NORMAL" when nothing crossed the threshold) --
this project has no existing convention for a more specific statistical
label, so per the Phase 4C spec, this generic one is used everywhere.

*** SOURCE SEPARATION ***
Every detection function below operates on ONE source's own time series at
a time (see `run_anomaly_detection`, which groups by `source` before
calling per-variable detectors). ERA5 and Open-Meteo observations are never
merged into one series and never compared directly against each other here
-- each source's rolling baseline is built purely from that source's own
past values. This also means the documented Phase 2C pressure caveat
(Open-Meteo's `surface_pressure` vs ERA5's `msl`, a ~35-46 hPa systematic
elevation offset -- see README.md) can never itself be mistaken for a
weather anomaly by this module: that offset only appears when comparing
the two sources to each other, which Phase 4C never does.

*** METHODS (summarized here; see README.md's Phase 4C section for the
full write-up with real-data results) ***
    - temperature, wind_speed, pressure: causal rolling z-score.
      |z| >= AnomalyConfig.z_threshold -> STATISTICAL_ANOMALY.
    - rainfall: causal rolling-percentile method (NOT z-score -- rainfall
      is zero-inflated, see `detect_rainfall_anomalies`'s docstring).

All thresholds, window sizes, and severity breakpoints live in
`AnomalyConfig` -- nothing here is an unexplained magic number.
"""
from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field, asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fusion.temporal_alignment import check_temporal_match, DEFAULT_MAX_TIME_DIFF_MINUTES
from fusion.spatial_alignment import check_spatial_match, DEFAULT_MAX_DISTANCE_KM

from phase4c.anomaly_features import (
    causal_rolling_mean_std, causal_rolling_quantiles,
    safe_zscore, is_effectively_zero_variance,
)
from phase4c.anomaly_scoring import (
    severity_from_ratio,
    explain_zscore, explain_rainfall, explain_insufficient_history,
    explain_zero_variance, explain_missing_value, explain_invalid_value,
    CLASSIFICATION_STATISTICAL_ANOMALY, CLASSIFICATION_NORMAL,
    STATUS_EVALUATED, STATUS_INSUFFICIENT_HISTORY, STATUS_ZERO_VARIANCE,
    STATUS_MISSING_VALUE, STATUS_INVALID_VALUE,
)


# ---------------------------------------------------------------------------
# Configuration -- every number the detectors use lives here, documented.
# ---------------------------------------------------------------------------

@dataclass
class AnomalyConfig:
    # --- temperature / wind_speed / pressure: rolling z-score ---
    zscore_window: int = 168          # 7 days of hourly data
    zscore_min_periods: int = 168     # require a full 7-day causal history before scoring
    z_threshold: float = 3.0          # classic "three-sigma" outlier convention
    zero_variance_epsilon: float = 1e-6  # rolling std below this is treated as undefined, not divided by

    # --- rainfall: rolling percentile (zero-inflation-aware) ---
    rainfall_window: int = 720        # 30 days -- percentiles need more history than a mean/std
    rainfall_min_periods: int = 168   # but only require 1 week before the first score is attempted
    rainfall_upper_quantile: float = 0.95   # the "usually-not-raining-this-much" reference line
    rainfall_threshold: float = 1.0   # score >= 1.0 * (p95 - p50 gap) beyond p95 -> anomaly
    rainfall_epsilon: float = 0.1     # mm; matches typical rain-gauge/reanalysis resolution, avoids div-by-0

    # --- severity: score expressed as a ratio of its own base threshold ---
    severity_ratio_low: float = 2.0     # [1x, 2x) threshold -> LOW
    severity_ratio_medium: float = 3.0  # [2x, 3x) threshold -> MEDIUM
    severity_ratio_high: float = 4.0    # [3x, 4x) threshold -> HIGH, >=4x -> CRITICAL


DEFAULT_CONFIG = AnomalyConfig()

VARIABLES = ("temperature", "wind_speed", "rainfall", "pressure")


# ---------------------------------------------------------------------------
# The anomaly record itself
# ---------------------------------------------------------------------------

@dataclass
class AnomalyRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    timestamp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location: Optional[str] = None            # human-readable "city, state, country" when available

    source: Optional[str] = None              # "ERA5" | "Open-Meteo" | ... -- never mixed
    variable: Optional[str] = None            # "temperature" | "wind_speed" | "rainfall" | "pressure"

    observed_value: Optional[float] = None
    baseline_value: Optional[float] = None    # rolling mean (z-score vars) or rolling p95 (rainfall)
    rolling_reference: Dict[str, Any] = field(default_factory=dict)  # full stat breakdown, method-specific
    deviation: Optional[float] = None         # observed - baseline_value

    method: Optional[str] = None              # "rolling_zscore" | "rolling_percentile"
    threshold: Optional[float] = None
    anomaly_score: Optional[float] = None     # None when status != EVALUATED -- never fabricated

    severity: Optional[str] = None            # LOW/MEDIUM/HIGH/CRITICAL, or None if not anomalous
    classification: str = CLASSIFICATION_NORMAL   # STATISTICAL_ANOMALY | NORMAL -- never a disaster label
    status: str = STATUS_EVALUATED            # EVALUATED | INSUFFICIENT_HISTORY | ZERO_VARIANCE | MISSING_VALUE | INVALID_VALUE

    explanation: str = ""
    supporting_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Preparing a source's records into a sorted, deduplicated DataFrame
# ---------------------------------------------------------------------------

def records_to_dataframe(records: List[Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Converts a list of WeatherRecord objects/dicts (all from the SAME
    source) into a DataFrame sorted by timestamp ascending, with duplicate
    timestamps resolved by keeping the first occurrence.

    Returns (dataframe, prep_summary) where prep_summary documents what was
    done (duplicate/unsorted/missing-source-consistency counts) so callers
    can report it honestly rather than silently dropping data.
    """
    rows = []
    for r in records:
        d = r if isinstance(r, dict) else r.to_dict()
        rows.append({
            "timestamp": d.get("timestamp"),
            "source": d.get("source"),
            "latitude": d.get("latitude"),
            "longitude": d.get("longitude"),
            "country": d.get("country"),
            "state": d.get("state"),
            "district": d.get("district"),
            "city": d.get("city"),
            "temperature": d.get("temperature"),
            "wind_speed": d.get("wind_speed"),
            "rainfall": d.get("rainfall"),
            "pressure": d.get("pressure"),
        })
    df = pd.DataFrame(rows)
    prep_summary: Dict[str, Any] = {
        "input_records": len(df),
        "records_without_timestamp": int(df["timestamp"].isna().sum()) if len(df) else 0,
        "duplicate_timestamps_dropped": 0,
        "was_unsorted": False,
        "sources_present": sorted(df["source"].dropna().unique().tolist()) if len(df) else [],
    }
    if df.empty:
        return df, prep_summary

    df = df[df["timestamp"].notna()].copy()
    df["_ts_parsed"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df[df["_ts_parsed"].notna()].copy()

    was_sorted = df["_ts_parsed"].is_monotonic_increasing
    prep_summary["was_unsorted"] = not was_sorted
    df = df.sort_values("_ts_parsed", kind="mergesort")

    before = len(df)
    df = df.drop_duplicates(subset=["_ts_parsed"], keep="first")
    prep_summary["duplicate_timestamps_dropped"] = before - len(df)

    df = df.reset_index(drop=True)

    # Invalid rainfall (negative) is physically impossible -- flagged and
    # excluded from both scoring and the rolling baseline, never silently
    # merged into the "normal" distribution.
    invalid_rainfall_mask = df["rainfall"].notna() & (df["rainfall"] < 0)
    prep_summary["invalid_rainfall_count"] = int(invalid_rainfall_mask.sum())
    df.loc[invalid_rainfall_mask, "_rainfall_invalid"] = True
    df["_rainfall_invalid"] = df.get("_rainfall_invalid", False).fillna(False)
    df.loc[invalid_rainfall_mask, "rainfall"] = np.nan

    return df, prep_summary


def _location_string(row: pd.Series) -> Optional[str]:
    parts = [row.get("city"), row.get("state"), row.get("country")]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None


# ---------------------------------------------------------------------------
# Rolling z-score detector (temperature / wind_speed / pressure)
# ---------------------------------------------------------------------------

def detect_zscore_variable(
    df: pd.DataFrame, variable: str, config: AnomalyConfig = DEFAULT_CONFIG,
    pressure_caveat: bool = False,
) -> List[AnomalyRecord]:
    """Rolling z-score anomaly detection for a single variable column of an
    already-sorted, already-deduplicated, single-source DataFrame (see
    `records_to_dataframe`). Used for temperature, wind_speed, and
    (with `pressure_caveat=True`, which only adds a documentation note to
    the explanation -- it changes no numbers) pressure.
    """
    if df.empty or variable not in df.columns:
        return []

    series = df[variable]
    roll_mean, roll_std = causal_rolling_mean_std(series, config.zscore_window, config.zscore_min_periods)

    records: List[AnomalyRecord] = []
    for i in range(len(df)):
        row = df.iloc[i]
        observed = row[variable]
        base_kwargs = dict(
            timestamp=row["timestamp"], latitude=row["latitude"], longitude=row["longitude"],
            location=_location_string(row), source=row["source"], variable=variable,
            method="rolling_zscore", threshold=config.z_threshold,
        )

        if pd.isna(observed):
            records.append(AnomalyRecord(
                **base_kwargs, status=STATUS_MISSING_VALUE, classification=CLASSIFICATION_NORMAL,
                explanation=explain_missing_value(variable),
            ))
            continue

        mean_i, std_i = roll_mean.iloc[i], roll_std.iloc[i]

        # Count valid prior observations actually available in the window,
        # for an honest INSUFFICIENT_HISTORY explanation.
        window_slice = series.iloc[max(0, i - config.zscore_window):i]
        available = int(window_slice.notna().sum())

        if pd.isna(mean_i) or pd.isna(std_i):
            records.append(AnomalyRecord(
                **base_kwargs, observed_value=float(observed),
                status=STATUS_INSUFFICIENT_HISTORY, classification=CLASSIFICATION_NORMAL,
                explanation=explain_insufficient_history(
                    variable, config.zscore_window, config.zscore_min_periods, available
                ),
                supporting_context={"available_prior_observations": available},
            ))
            continue

        if is_effectively_zero_variance(std_i, config.zero_variance_epsilon):
            records.append(AnomalyRecord(
                **base_kwargs, observed_value=float(observed), baseline_value=float(mean_i),
                rolling_reference={"rolling_mean": float(mean_i), "rolling_std": float(std_i)},
                status=STATUS_ZERO_VARIANCE, classification=CLASSIFICATION_NORMAL,
                explanation=explain_zero_variance(variable, mean_i, config.zscore_window, config.zero_variance_epsilon),
            ))
            continue

        z = safe_zscore(observed, mean_i, std_i)
        is_anomaly = abs(z) >= config.z_threshold
        severity = None
        if is_anomaly:
            ratio = abs(z) / config.z_threshold
            severity = severity_from_ratio(
                ratio, config.severity_ratio_low, config.severity_ratio_medium, config.severity_ratio_high
            )

        explanation = explain_zscore(
            variable, observed, mean_i, std_i, z, config.z_threshold, severity,
            config.zscore_window, "rolling_zscore",
        )
        if pressure_caveat:
            explanation += (
                " [Pressure caveat: this baseline is built purely from this source's own past "
                "pressure values -- ERA5 uses mean-sea-level pressure (msl) and Open-Meteo uses "
                "surface_pressure; the two are never compared to each other here, so the known "
                "~35-46 hPa elevation-offset mismatch between them (see README.md, Phase 2C) "
                "cannot itself cause a false anomaly.]"
            )

        records.append(AnomalyRecord(
            **base_kwargs, observed_value=float(observed), baseline_value=float(mean_i),
            rolling_reference={"rolling_mean": float(mean_i), "rolling_std": float(std_i)},
            deviation=float(observed - mean_i),
            anomaly_score=float(z), severity=severity,
            classification=CLASSIFICATION_STATISTICAL_ANOMALY if is_anomaly else CLASSIFICATION_NORMAL,
            status=STATUS_EVALUATED, explanation=explanation,
            supporting_context={"available_prior_observations": available},
        ))

    return records


# ---------------------------------------------------------------------------
# Rolling percentile detector (rainfall)
# ---------------------------------------------------------------------------

def detect_rainfall_anomalies(
    df: pd.DataFrame, config: AnomalyConfig = DEFAULT_CONFIG,
) -> List[AnomalyRecord]:
    """Rainfall-specific anomaly detection using a rolling-percentile
    method rather than a z-score.

    WHY NOT Z-SCORE: rainfall is zero-inflated -- most hours have 0 mm of
    rain, so the rolling mean sits near 0 and the rolling std is small.
    Under an ordinary z-score, an entirely ordinary rain shower would
    already look like an extreme statistical outlier, and the method would
    systematically over-flag "it rained" as anomalous rather than "it
    rained unusually heavily". A percentile-based method sidesteps this:
    the rolling 95th percentile (`rainfall_upper_quantile`) already
    reflects "how much rain is unusually heavy FOR THIS LOCATION/SEASON'S
    OWN RECENT HISTORY", including the zeros, without assuming a normal
    distribution.

    score = (observed - p95) / max(p95 - p50, epsilon); anomaly when
    score >= config.rainfall_threshold.
    """
    if df.empty or "rainfall" not in df.columns:
        return []

    series = df["rainfall"]
    p50_roll, p95_roll = causal_rolling_quantiles(
        series, config.rainfall_window, config.rainfall_min_periods,
        quantiles=(0.5, config.rainfall_upper_quantile),
    )

    records: List[AnomalyRecord] = []
    for i in range(len(df)):
        row = df.iloc[i]
        observed = row["rainfall"]
        base_kwargs = dict(
            timestamp=row["timestamp"], latitude=row["latitude"], longitude=row["longitude"],
            location=_location_string(row), source=row["source"], variable="rainfall",
            method="rolling_percentile", threshold=config.rainfall_threshold,
        )

        if bool(row.get("_rainfall_invalid", False)):
            records.append(AnomalyRecord(
                **base_kwargs, status=STATUS_INVALID_VALUE, classification=CLASSIFICATION_NORMAL,
                explanation=explain_invalid_value("rainfall", float("nan"), "negative rainfall is not physically possible"),
            ))
            continue

        if pd.isna(observed):
            records.append(AnomalyRecord(
                **base_kwargs, status=STATUS_MISSING_VALUE, classification=CLASSIFICATION_NORMAL,
                explanation=explain_missing_value("rainfall"),
            ))
            continue

        p50_i, p95_i = p50_roll.iloc[i], p95_roll.iloc[i]
        window_slice = series.iloc[max(0, i - config.rainfall_window):i]
        available = int(window_slice.notna().sum())

        if pd.isna(p50_i) or pd.isna(p95_i):
            records.append(AnomalyRecord(
                **base_kwargs, observed_value=float(observed),
                status=STATUS_INSUFFICIENT_HISTORY, classification=CLASSIFICATION_NORMAL,
                explanation=explain_insufficient_history(
                    "rainfall", config.rainfall_window, config.rainfall_min_periods, available
                ),
                supporting_context={"available_prior_observations": available},
            ))
            continue

        gap = max(p95_i - p50_i, config.rainfall_epsilon)
        score = (observed - p95_i) / gap
        is_anomaly = observed > p95_i and score >= config.rainfall_threshold
        severity = None
        if is_anomaly:
            ratio = score / config.rainfall_threshold
            severity = severity_from_ratio(
                ratio, config.severity_ratio_low, config.severity_ratio_medium, config.severity_ratio_high
            )

        explanation = explain_rainfall(
            observed, p50_i, p95_i, score, config.rainfall_threshold, severity,
            config.rainfall_window, config.rainfall_epsilon,
        )

        records.append(AnomalyRecord(
            **base_kwargs, observed_value=float(observed), baseline_value=float(p95_i),
            rolling_reference={"rolling_median_p50": float(p50_i), "rolling_p95": float(p95_i)},
            deviation=float(observed - p95_i),
            anomaly_score=float(score), severity=severity,
            classification=CLASSIFICATION_STATISTICAL_ANOMALY if is_anomaly else CLASSIFICATION_NORMAL,
            status=STATUS_EVALUATED, explanation=explanation,
            supporting_context={"available_prior_observations": available},
        ))

    return records


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_anomaly_detection_for_source(
    records: List[Any], config: AnomalyConfig = DEFAULT_CONFIG,
) -> Tuple[List[AnomalyRecord], Dict[str, Any]]:
    """Runs all four variable detectors over ONE source's records. Returns
    (all_anomaly_records_including_non_anomalous, prep_summary)."""
    df, prep_summary = records_to_dataframe(records)
    if df.empty:
        return [], prep_summary

    all_records: List[AnomalyRecord] = []
    all_records += detect_zscore_variable(df, "temperature", config)
    all_records += detect_zscore_variable(df, "wind_speed", config)
    all_records += detect_zscore_variable(df, "pressure", config, pressure_caveat=True)
    all_records += detect_rainfall_anomalies(df, config)
    return all_records, prep_summary


def run_anomaly_detection(
    records: List[Any], config: AnomalyConfig = DEFAULT_CONFIG,
) -> Tuple[List[AnomalyRecord], Dict[str, Any]]:
    """Top-level entry point: groups arbitrary (possibly multi-source)
    WeatherRecord input by `source` and runs detection independently per
    source (see module docstring, "SOURCE SEPARATION"). Returns
    (all_anomaly_records, prep_summary_by_source)."""
    by_source: Dict[str, List[Any]] = {}
    for r in records:
        d = r if isinstance(r, dict) else r.to_dict()
        by_source.setdefault(d.get("source") or "UNKNOWN", []).append(r)

    all_records: List[AnomalyRecord] = []
    prep_summary_by_source: Dict[str, Any] = {}
    for source_name, source_records in by_source.items():
        recs, prep = run_anomaly_detection_for_source(source_records, config)
        all_records += recs
        prep_summary_by_source[source_name] = prep

    return all_records, prep_summary_by_source


# ---------------------------------------------------------------------------
# Phase 4A integration -- additive, does not modify WeatherIntelligence
# ---------------------------------------------------------------------------

def find_matching_anomalies(
    timestamp: Optional[str], latitude: Optional[float], longitude: Optional[float],
    anomaly_records: List[AnomalyRecord],
    max_time_diff_minutes: float = DEFAULT_MAX_TIME_DIFF_MINUTES,
    max_distance_km: float = DEFAULT_MAX_DISTANCE_KM,
) -> List[AnomalyRecord]:
    """Selects which already-computed AnomalyRecords belong to a given
    time/place, reusing Phase 2B's own check_temporal_match/
    check_spatial_match -- the exact same alignment functions Phase 4A's
    `select_report_evidence` already uses for report evidence. Only
    STATISTICAL_ANOMALY-classified records are returned (NORMAL/
    INSUFFICIENT_HISTORY/etc. records are not "matches" worth attaching)."""
    if timestamp is None or latitude is None or longitude is None:
        return []
    matches = []
    for a in anomaly_records:
        if a.classification != CLASSIFICATION_STATISTICAL_ANOMALY:
            continue
        if a.timestamp is None or a.latitude is None or a.longitude is None:
            continue
        temporal = check_temporal_match(timestamp, a.timestamp, max_time_diff_minutes)
        if not temporal.is_match:
            continue
        spatial = check_spatial_match(latitude, longitude, a.latitude, a.longitude, max_distance_km)
        if not spatial.is_match:
            continue
        matches.append(a)
    return matches


def attach_anomalies_to_intelligence(intel: Any, anomaly_records: List[AnomalyRecord]) -> Any:
    """Returns a COPY of a Phase 4A `WeatherIntelligence` object with its
    already-existing, previously-unpopulated `anomaly` field filled in --
    additive integration per the Phase 4C spec ("Phase 4A already contains
    an anomaly placeholder... integrate ADDITIVELY... do not redesign
    WeatherIntelligence"). Never fabricates a match: if no anomaly aligns
    in time/place with this intelligence record, `anomaly` stays None,
    exactly as Phase 4A left it."""
    matches = find_matching_anomalies(intel.timestamp, intel.latitude, intel.longitude, anomaly_records)
    if not matches:
        return replace(intel, anomaly=None)
    anomaly_payload = {
        "matched_anomaly_count": len(matches),
        "anomalies": [
            {
                "variable": m.variable, "source": m.source, "severity": m.severity,
                "classification": m.classification, "anomaly_score": m.anomaly_score,
                "method": m.method, "explanation": m.explanation,
            }
            for m in matches
        ],
        "note": (
            "These are STATISTICAL_ANOMALY findings from Phase 4C's rolling-baseline detectors -- "
            "not a disaster/emergency/extreme-event judgment. See each entry's own explanation."
        ),
    }
    return replace(intel, anomaly=anomaly_payload)


# ---------------------------------------------------------------------------
# Phase 4B integration -- additive context, never conflating forecast with observation
# ---------------------------------------------------------------------------

def attach_anomaly_context_to_forecast(
    forecast_record: Dict[str, Any], anomaly_records: List[AnomalyRecord],
    max_time_diff_minutes: float = DEFAULT_MAX_TIME_DIFF_MINUTES,
    max_distance_km: float = DEFAULT_MAX_DISTANCE_KM,
) -> Dict[str, Any]:
    """Given one Phase 4B forecast record (a dict with its own
    `timestamp`/`latitude`/`longitude`), returns a NEW dict with an added
    `observed_anomaly_context` key listing any observed STATISTICAL_ANOMALY
    findings near that same time/place -- for analytics context only.

    This function never edits the forecast's own predicted value and never
    labels a forecasted value itself as an observed anomaly -- forecast and
    observation stay conceptually separate, per the Phase 4C spec."""
    ts = forecast_record.get("timestamp")
    lat = forecast_record.get("latitude")
    lon = forecast_record.get("longitude")
    matches = find_matching_anomalies(ts, lat, lon, anomaly_records, max_time_diff_minutes, max_distance_km)
    out = dict(forecast_record)
    out["observed_anomaly_context"] = [
        {"variable": m.variable, "source": m.source, "severity": m.severity, "anomaly_score": m.anomaly_score}
        for m in matches
    ]
    return out
