"""
Source comparison: for a pair of (ERA5, IMD) records already checked for
temporal/spatial compatibility, compute per-variable differences and an
agreement classification.

AGREEMENT THRESHOLDS -- documented assumption, not a scientific constant.
Percentage difference is computed against the larger-magnitude-safe
denominator (see _percent_diff). Thresholds below are deliberately simple
and stated explicitly so they can be revisited with real multi-station data:

    percent_diff < 5%   -> SOURCE_AGREEMENT_HIGH
    percent_diff < 15%  -> SOURCE_AGREEMENT_MEDIUM
    percent_diff >= 15% -> SOURCE_DISAGREEMENT

Rainfall is handled specially: percent difference is not meaningful when one
or both values are at or near zero (a wet/dry disagreement of 0mm vs 0.2mm is
a 100%+ "difference" that is not physically significant), so rainfall
agreement uses an absolute-mm threshold instead of a percentage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any

EPSILON = 1e-6

PERCENT_THRESHOLDS = {
    "high": 5.0,     # < 5% difference
    "medium": 15.0,  # < 15% difference
}

# Rainfall uses an absolute mm threshold instead of percent (see module docstring)
RAINFALL_ABS_THRESHOLDS_MM = {
    "high": 1.0,
    "medium": 5.0,
}


@dataclass
class VariableComparison:
    variable: str
    era5_value: Optional[float]
    imd_value: Optional[float]
    absolute_difference: Optional[float]
    percent_difference: Optional[float]  # None for rainfall (uses absolute instead) or if not computable
    agreement_flag: str  # SOURCE_AGREEMENT_HIGH | _MEDIUM | SOURCE_DISAGREEMENT | SOURCE_COMPARISON_UNAVAILABLE


def _percent_diff(a: float, b: float) -> float:
    denom = max(abs(a), abs(b), EPSILON)
    return abs(a - b) / denom * 100.0


def compare_variable(variable: str, era5_value: Optional[float], imd_value: Optional[float]) -> VariableComparison:
    if era5_value is None or imd_value is None:
        return VariableComparison(variable, era5_value, imd_value, None, None, "SOURCE_COMPARISON_UNAVAILABLE")

    abs_diff = round(abs(era5_value - imd_value), 4)

    if variable == "rainfall":
        if abs_diff < RAINFALL_ABS_THRESHOLDS_MM["high"]:
            flag = "SOURCE_AGREEMENT_HIGH"
        elif abs_diff < RAINFALL_ABS_THRESHOLDS_MM["medium"]:
            flag = "SOURCE_AGREEMENT_MEDIUM"
        else:
            flag = "SOURCE_DISAGREEMENT"
        return VariableComparison(variable, era5_value, imd_value, abs_diff, None, flag)

    pct_diff = round(_percent_diff(era5_value, imd_value), 3)
    if pct_diff < PERCENT_THRESHOLDS["high"]:
        flag = "SOURCE_AGREEMENT_HIGH"
    elif pct_diff < PERCENT_THRESHOLDS["medium"]:
        flag = "SOURCE_AGREEMENT_MEDIUM"
    else:
        flag = "SOURCE_DISAGREEMENT"

    return VariableComparison(variable, era5_value, imd_value, abs_diff, pct_diff, flag)


def compare_records(era5_record, imd_record) -> Dict[str, VariableComparison]:
    """Compare all shared comparable variables between an ERA5 WeatherRecord
    and an IMD WeatherRecord. Returns a dict keyed by variable name."""
    variables = ["temperature", "pressure", "rainfall", "wind_speed"]
    return {
        var: compare_variable(var, getattr(era5_record, var, None), getattr(imd_record, var, None))
        for var in variables
    }
