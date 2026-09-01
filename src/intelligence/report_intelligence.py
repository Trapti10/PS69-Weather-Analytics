"""
Phase 3B orchestration: runs the full intelligence pipeline over a batch of
already-validated/normalized/deduplicated WeatherReport objects (Phase 3A's
output), in the order specified by the Phase 3B architecture:

    Exact Dedup (Phase 3A, already done before this module is called)
        -> Semantic Similarity
        -> Event Classification
        -> Risk / Suspicion Scoring
        -> Intelligent WeatherReport (same object, more fields populated)

This module does not re-implement any of Phase 3A's ingestion/validation/
normalization/exact-dedup logic -- callers (e.g. scripts/run_phase3b_demo.py)
are expected to have already run that, exactly as Phase 3A's own demo does.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_report import WeatherReport
from intelligence.semantic_similarity import compute_semantic_similarity
from intelligence.event_classifier import (
    build_training_set, evaluate_classifier_leave_one_out, classify_reports, MIN_TOTAL_EXAMPLES_TO_TRAIN,
)
from intelligence.report_risk import score_reports_risk


def run_intelligence_pipeline(reports: List[WeatherReport]) -> Dict[str, Any]:
    """Runs semantic similarity -> event classification -> risk scoring over
    `reports` (mutated in place, same objects returned). Returns a dict with
    the classifier's LOOCV evaluation (or an explicit "not enough data"
    marker) alongside the processed reports, so callers can report real
    metrics without re-deriving them."""

    # ---- Semantic similarity (reuses Phase 3A's exact time/location buckets) ----
    reports = compute_semantic_similarity(reports)

    # ---- Event classification ----
    texts, labels = build_training_set(reports)
    class_counts = {c: labels.count(c) for c in sorted(set(labels))}

    if len(texts) < MIN_TOTAL_EXAMPLES_TO_TRAIN:
        classifier_eval = None
        reports = classify_reports(reports, training_texts=texts, training_labels=labels)
    else:
        classifier_eval = evaluate_classifier_leave_one_out(texts, labels)
        reports = classify_reports(reports, training_texts=texts, training_labels=labels)

    # ---- Risk / suspicion scoring (reuses the same bucketing again) ----
    reports = score_reports_risk(reports)

    return {
        "reports": reports,
        "classifier_training_size": len(texts),
        "classifier_class_counts": class_counts,
        "classifier_evaluation": classifier_eval,  # None if too small to evaluate
    }
