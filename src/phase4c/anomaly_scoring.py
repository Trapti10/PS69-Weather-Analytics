"""
Phase 4C -- Severity classification and deterministic explanation text.

Kept separate from anomaly_detection.py so the "how do we turn a numeric
deviation into LOW/MEDIUM/HIGH/CRITICAL and a human-readable sentence"
logic is in one place, independent of *which* statistical method produced
the deviation. Every threshold used here comes from `AnomalyConfig`
(defined in anomaly_detection.py) -- nothing is hard-coded in this file.

Severity is a step function of "how many multiples of the base anomaly
threshold was this deviation": scores in [1x, 2x) threshold => LOW,
[2x, 3x) => MEDIUM, [3x, 4x) => HIGH, >= 4x => CRITICAL. This is a simple,
transparent, documented convention -- NOT a claim that e.g. "HIGH" means
any specific real-world danger level. See README.md's Phase 4C section for
the full justification and worked examples.
"""
from __future__ import annotations

from typing import Optional


SEVERITY_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

CLASSIFICATION_STATISTICAL_ANOMALY = "STATISTICAL_ANOMALY"
CLASSIFICATION_NORMAL = "NORMAL"

STATUS_EVALUATED = "EVALUATED"
STATUS_INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
STATUS_ZERO_VARIANCE = "ZERO_VARIANCE"
STATUS_MISSING_VALUE = "MISSING_VALUE"
STATUS_INVALID_VALUE = "INVALID_VALUE"


def severity_from_ratio(ratio: float, low: float, medium: float, high: float) -> str:
    """`ratio` = (score / base_threshold), i.e. "how many multiples of the
    configured base threshold". `low`, `medium`, `high` are the configured
    ratio breakpoints (AnomalyConfig.severity_ratio_low/medium/high) --
    ratio >= high -> CRITICAL, >= medium -> HIGH, >= low -> MEDIUM,
    otherwise (ratio >= 1, since the caller only invokes this once a
    variable has already crossed the base threshold) -> LOW.
    """
    if ratio >= high:
        return "CRITICAL"
    if ratio >= medium:
        return "HIGH"
    if ratio >= low:
        return "MEDIUM"
    return "LOW"


def explain_zscore(
    variable: str, observed: float, baseline_mean: float, baseline_std: float,
    z: float, threshold: float, severity: Optional[str], window: int, method_name: str,
) -> str:
    result = CLASSIFICATION_STATISTICAL_ANOMALY if severity else CLASSIFICATION_NORMAL
    base = (
        f"Observed {variable} = {observed:.3f}. "
        f"Rolling baseline (mean of the previous {window} valid observations) = {baseline_mean:.3f}, "
        f"rolling std = {baseline_std:.3f}. "
        f"z-score = ({observed:.3f} - {baseline_mean:.3f}) / {baseline_std:.3f} = {z:.3f}. "
        f"Threshold = |z| >= {threshold}. Method = {method_name}. Result = {result}."
    )
    if severity:
        base += f" Severity = {severity}."
    return base


def explain_rainfall(
    observed: float, p50: float, p95: float, score: float, threshold: float,
    severity: Optional[str], window: int, epsilon: float,
) -> str:
    result = CLASSIFICATION_STATISTICAL_ANOMALY if severity else CLASSIFICATION_NORMAL
    gap = max(p95 - p50, epsilon)
    base = (
        f"Observed rainfall = {observed:.3f} mm. "
        f"Rolling median (previous {window} valid observations) = {p50:.3f} mm, "
        f"rolling 95th percentile = {p95:.3f} mm. "
        f"Because rainfall is zero-inflated (most hours have 0 mm), an ordinary z-score would "
        f"treat small amounts of ordinary rain as extreme; instead the deviation is measured as "
        f"how far above the rolling 95th percentile the observation is, normalized by the "
        f"median-to-95th-percentile gap: score = (observed - p95) / max(p95 - p50, epsilon) = "
        f"({observed:.3f} - {p95:.3f}) / {gap:.3f} = {score:.3f}. "
        f"Threshold = score >= {threshold}. Method = rolling_percentile. Result = {result}."
    )
    if severity:
        base += f" Severity = {severity}."
    return base


def explain_insufficient_history(variable: str, window: int, min_periods: int, available: int) -> str:
    return (
        f"Not enough prior history to build a rolling baseline for {variable}: "
        f"{available} valid observation(s) available in the preceding {window}-row window, "
        f"but {min_periods} are required. Status = {STATUS_INSUFFICIENT_HISTORY}. "
        f"No anomaly score was computed -- fabricating one from insufficient evidence is not permitted."
    )


def explain_zero_variance(variable: str, baseline_mean: float, window: int, epsilon: float) -> str:
    return (
        f"The rolling window for {variable} has near-zero variance (std < {epsilon}), so a "
        f"z-score is undefined/unstable (division by ~0). Rolling baseline mean = {baseline_mean:.3f} "
        f"over the previous {window} valid observations. Status = {STATUS_ZERO_VARIANCE}. "
        f"No anomaly score was computed for this observation."
    )


def explain_missing_value(variable: str) -> str:
    return f"{variable} is missing (None/NaN) for this record. Status = {STATUS_MISSING_VALUE}."


def explain_invalid_value(variable: str, observed: float, reason: str) -> str:
    return (
        f"{variable} = {observed} was rejected as physically invalid ({reason}) and excluded "
        f"from both scoring and the rolling baseline. Status = {STATUS_INVALID_VALUE}."
    )
