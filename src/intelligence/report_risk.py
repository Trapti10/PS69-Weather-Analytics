"""
Risk/suspicion intelligence for WeatherReport objects (Phase 3B).

*** "SUSPICIOUS" IS NOT "FAKE" -- READ THIS BEFORE USING risk_label ***
This module never declares a report fake, false, or verified-true. It
produces a risk_score (0-1), a risk_label (LOW_RISK / MEDIUM_RISK /
HIGH_RISK / UNVERIFIED), and risk_reasons -- a transparent, itemized list
of WHY, so a human reviewer can see the actual contributing signals rather
than trust an opaque number. A HIGH_RISK label means "several independent
data-quality/reliability signals are present, review before acting on
this," not "this is confirmed misinformation." Phase 3A's own
verification_status vocabulary (UNVERIFIED/VERIFIED/REJECTED/SUSPICIOUS)
is untouched by this module; risk_label is a SEPARATE, complementary
signal, not a replacement.

*** SIGNALS USED (explainable, weighted, all stated assumptions) ***
Each signal below adds a fixed, documented amount to risk_score (capped at
1.0). Weights are deliberately simple and interpretable rather than fit to
any real outcome data (none exists yet) -- this is an engineering baseline,
not a calibrated risk model:
    - verification_status == "REJECTED"      -> risk_score forced to 1.0, HIGH_RISK, short-circuits everything else
    - is_suspicious (Phase 3A's own flag)     -> +0.35
    - source_reliability < 0.35               -> +0.25 (SOCIAL_MEDIA's default baseline is 0.30 -- this
                                                  is a real, common case, not a rare edge case)
    - event_classification_confidence < 0.30  -> +0.15 (classifier itself is unsure what this report describes)
    - semantic conflict in the same bucket    -> +0.30 (see below)

*** REAL FINDING FROM AN ACTUAL RUN: THE CONFIDENCE SIGNAL FIRES ALMOST UNIVERSALLY ***
At this project's current sample size (~21 labeled examples across 8
classes), the classifier's own max-class probability is low for nearly
EVERY report (observed range ~0.19-0.30 in the actual demo run), even ones
it classifies correctly. This means the "low classification confidence"
risk signal fires for almost all reports, which weakens its power to
actually DISCRIMINATE risky from non-risky reports right now -- it adds a
fairly uniform +0.15 rather than a selective one. This is not hidden or
patched around: it is a direct, expected consequence of training a
multi-class classifier on very few examples per class (a small-sample
classifier is rightly unsure of itself), and the honest fix is more
labeled data, not a recalibrated threshold that would just be curve-fit to
today's tiny fixture set.

*** "SEMANTIC CONFLICT" DEFINED ***
If two or more reports share the same time+location bucket (the exact
bucketing reused from report_dedup.py / semantic_similarity.py) but have
DIFFERENT event_type values (e.g. one says FLOODING, another says
HEATWAVE, for the same place and half-hour window), that is a real,
checkable contradiction worth surfacing -- not proof either is false, but
a legitimate reason for a human to look closer.

*** UNVERIFIED (risk sense) vs report.verification_status == "UNVERIFIED" ***
These are DIFFERENT things that happen to share a word, by this project's
own vocabulary choice (Part D of the Phase 3B spec explicitly lists
UNVERIFIED as a risk_label option). Here, risk_label = "UNVERIFIED" means
"not enough signal exists to compute a meaningful risk_score at all" (e.g.
empty text, so the classifier confidence signal doesn't exist, and no other
strong signal fired) -- risk_score is left as None in that case, not
fabricated as 0.0 or any other number.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_report import WeatherReport
from ingestion.report_dedup import _time_bucket, _location_bucket, DEFAULT_TIME_BUCKET_MINUTES, DEFAULT_LOCATION_DECIMALS

WEIGHT_IS_SUSPICIOUS = 0.35
WEIGHT_LOW_SOURCE_RELIABILITY = 0.25
LOW_SOURCE_RELIABILITY_THRESHOLD = 0.35
WEIGHT_LOW_CLASSIFICATION_CONFIDENCE = 0.15
LOW_CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.30
WEIGHT_SEMANTIC_CONFLICT = 0.30

RISK_LABEL_HIGH_THRESHOLD = 0.65
RISK_LABEL_MEDIUM_THRESHOLD = 0.35


def _find_semantic_conflicts(reports: List[WeatherReport],
                              time_bucket_minutes: int = DEFAULT_TIME_BUCKET_MINUTES,
                              location_decimals: int = DEFAULT_LOCATION_DECIMALS) -> Dict[str, bool]:
    """Returns {report_id: True/False} -- True if this report's event_type
    disagrees with at least one OTHER report in the same time+location
    bucket. Reuses the exact same bucketing as report_dedup/semantic_similarity."""
    buckets: Dict[str, List[WeatherReport]] = {}
    for r in reports:
        tbucket = _time_bucket(r.timestamp, time_bucket_minutes)
        lbucket = _location_bucket(r.latitude, r.longitude, location_decimals)
        key = f"{tbucket}|{lbucket}"
        buckets.setdefault(key, []).append(r)

    conflict: Dict[str, bool] = {r.report_id: False for r in reports}
    for bucket_reports in buckets.values():
        if len(bucket_reports) < 2:
            continue
        event_types = {r.event_type for r in bucket_reports if r.event_type}
        if len(event_types) > 1:
            for r in bucket_reports:
                conflict[r.report_id] = True

    return conflict


def score_report_risk(report: WeatherReport, has_semantic_conflict: bool) -> WeatherReport:
    """Sets risk_score / risk_label / risk_reasons on the given report.
    Mutates and returns the same object."""
    reasons: List[str] = []

    if report.verification_status == "REJECTED":
        report.risk_score = 1.0
        report.risk_label = "HIGH_RISK"
        report.risk_reasons = ["structurally rejected during Phase 3A validation "
                                f"({', '.join(report.quality_flags)})"]
        return report

    text_is_empty = not (report.text and len(report.text.strip()) >= 3)
    has_any_strong_signal = (
        report.is_suspicious
        or (report.source_reliability is not None and report.source_reliability < LOW_SOURCE_RELIABILITY_THRESHOLD)
        or has_semantic_conflict
    )

    if text_is_empty and report.event_classification_confidence is None and not has_any_strong_signal:
        report.risk_score = None
        report.risk_label = "UNVERIFIED"
        report.risk_reasons = ["insufficient content (no text, no classification signal) "
                                "to compute a meaningful risk score"]
        return report

    score = 0.0

    if report.is_suspicious:
        score += WEIGHT_IS_SUSPICIOUS
        reasons.append(f"flagged SUSPICIOUS during Phase 3A validation (+{WEIGHT_IS_SUSPICIOUS})")

    if report.source_reliability is not None and report.source_reliability < LOW_SOURCE_RELIABILITY_THRESHOLD:
        score += WEIGHT_LOW_SOURCE_RELIABILITY
        reasons.append(f"low baseline source reliability ({report.source_reliability}) "
                        f"(+{WEIGHT_LOW_SOURCE_RELIABILITY})")

    if (report.event_classification_confidence is not None
            and report.event_classification_confidence < LOW_CLASSIFICATION_CONFIDENCE_THRESHOLD):
        score += WEIGHT_LOW_CLASSIFICATION_CONFIDENCE
        reasons.append(f"low event-classification confidence ({report.event_classification_confidence}) "
                        f"(+{WEIGHT_LOW_CLASSIFICATION_CONFIDENCE})")

    if has_semantic_conflict:
        score += WEIGHT_SEMANTIC_CONFLICT
        reasons.append(f"conflicting event_type reported by another source in the same "
                        f"time+location window (+{WEIGHT_SEMANTIC_CONFLICT})")

    score = round(min(score, 1.0), 4)

    if score >= RISK_LABEL_HIGH_THRESHOLD:
        label = "HIGH_RISK"
    elif score >= RISK_LABEL_MEDIUM_THRESHOLD:
        label = "MEDIUM_RISK"
    else:
        label = "LOW_RISK"

    if not reasons:
        reasons.append("no risk signals triggered")

    report.risk_score = score
    report.risk_label = label
    report.risk_reasons = reasons
    return report


def score_reports_risk(reports: List[WeatherReport],
                        time_bucket_minutes: int = DEFAULT_TIME_BUCKET_MINUTES,
                        location_decimals: int = DEFAULT_LOCATION_DECIMALS) -> List[WeatherReport]:
    conflicts = _find_semantic_conflicts(reports, time_bucket_minutes, location_decimals)
    for r in reports:
        score_report_risk(r, conflicts.get(r.report_id, False))
        r.intelligence_processed_at = datetime.now(timezone.utc).isoformat()
    return reports
