#!/usr/bin/env python3
"""
Phase 3B demonstration: semantic similarity + ML event classification +
explainable risk scoring, on top of Phase 3A's already-validated,
normalized, exact-deduplicated synthetic report fixtures.

*** HONESTY NOTE ***
Same synthetic/demo fixtures as Phase 3A (now extended per Part G with
broader category coverage and dedicated semantic-duplicate/unrelated
cases) -- no live social media or citizen-app access exists. All numbers
below come from an actual run against this actual data, not invented.
"""
import sys
from pathlib import Path
from collections import Counter
import pickle
import json as jsonlib
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from adapters.social_report_adapter import social_fixture_to_reports
from adapters.citizen_report_adapter import citizen_fixture_to_reports
from ingestion.report_validators import validate_reports
from ingestion.report_normalizer import normalize_reports
from ingestion.report_dedup import detect_duplicates
from intelligence.report_intelligence import run_intelligence_pipeline
from intelligence.intelligence_storage import save_intelligent_reports_json, save_intelligent_reports_csv
from intelligence.event_classifier import build_training_set, train_final_classifier

MODELS_DIR = Path(__file__).resolve().parents[1] / "models" / "phase3b"


def print_section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def main():
    print_section("PHASE 3B -- Running Phase 3A pipeline first (unmodified)")
    social_reports = social_fixture_to_reports()
    citizen_reports = citizen_fixture_to_reports()
    all_reports = social_reports + citizen_reports
    all_reports = validate_reports(all_reports)
    all_reports = normalize_reports(all_reports)
    all_reports = detect_duplicates(all_reports)
    print(f"Phase 3A output: {len(all_reports)} reports "
          f"({len(social_reports)} social + {len(citizen_reports)} citizen)")

    print_section("PHASE 3B -- Semantic similarity + event classification + risk scoring")
    result = run_intelligence_pipeline(all_reports)
    all_reports = result["reports"]

    # ---------------- Semantic similarity summary ----------------
    print_section("Semantic similarity results")
    sim_counts = Counter(r.semantic_duplicate_status for r in all_reports)
    for status in ("EXACT_DUPLICATE", "SEMANTIC_DUPLICATE", "POSSIBLE_RELATED_EVENT", "UNRELATED", None):
        if status in sim_counts:
            print(f"  {str(status):24s}: {sim_counts[status]}")
    print()
    for r in all_reports:
        if r.semantic_duplicate_status in ("SEMANTIC_DUPLICATE", "POSSIBLE_RELATED_EVENT"):
            src = r.raw_payload.get("post_id") or r.raw_payload.get("report_id_raw")
            print(f"  {src:18s} -> {r.semantic_duplicate_status} (score={r.semantic_similarity_score}) "
                  f"matched={str(r.matched_report_id)[:8]}")

    # ---------------- Event classification summary ----------------
    print_section("Event classification (TF-IDF + Logistic Regression, LOOCV-evaluated)")
    print(f"Training set size: {result['classifier_training_size']} labeled examples")
    print(f"Class counts: {result['classifier_class_counts']}")
    if result["classifier_evaluation"] is None:
        print("Too few examples to train/evaluate a classifier "
              "(min required: see event_classifier.MIN_TOTAL_EXAMPLES_TO_TRAIN). "
              "predicted_event_category left as None for all reports.")
    else:
        ev = result["classifier_evaluation"]
        print(f"\n*** {ev.warning} ***\n")
        print(f"Accuracy (LOOCV):          {ev.accuracy}")
        print(f"Precision (macro, LOOCV):  {ev.precision_macro}")
        print(f"Recall (macro, LOOCV):     {ev.recall_macro}")
        print(f"F1 (macro, LOOCV):         {ev.f1_macro}")
        print(f"\nConfusion matrix (rows=true, cols=predicted), labels={ev.confusion_matrix_labels}:")
        for row in ev.confusion_matrix:
            print(f"  {row}")

    predicted_counts = Counter(r.predicted_event_category for r in all_reports)
    print(f"\nPredicted categories across all reports: {dict(predicted_counts)}")

    # ---------------- Risk scoring summary ----------------
    print_section("Risk / suspicion scoring")
    risk_counts = Counter(r.risk_label for r in all_reports)
    for label in ("LOW_RISK", "MEDIUM_RISK", "HIGH_RISK", "UNVERIFIED"):
        print(f"  {label:12s}: {risk_counts.get(label, 0)}")
    print()
    for r in all_reports:
        if r.risk_label in ("HIGH_RISK", "MEDIUM_RISK"):
            src = r.raw_payload.get("post_id") or r.raw_payload.get("report_id_raw")
            print(f"  {src:18s} -> {r.risk_label} (score={r.risk_score}) reasons={r.risk_reasons}")

    # ---------------- Overall summary ----------------
    print_section("Summary")
    confidences = [r.event_classification_confidence for r in all_reports
                   if r.event_classification_confidence is not None]
    avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else None

    print(f"Total reports: {len(all_reports)}")
    print(f"\nSemantic similarity: {dict(sim_counts)}")
    print(f"\nEvent classification (predicted): {dict(predicted_counts)}")
    print(f"Average classification confidence: {avg_conf}")
    print(f"\nRisk: {dict(risk_counts)}")

    # ---------------- Save ----------------
    print_section("Saving Phase 3B outputs to data/phase3b/ (new directory)")
    p1 = save_intelligent_reports_json(all_reports)
    p2 = save_intelligent_reports_csv(all_reports)
    for p in (p1, p2):
        print(f"  {p}")

    print_section("Saving trained classifier to models/phase3b/ (Part K)")
    texts, labels = build_training_set(all_reports)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if len(texts) >= 6:  # same MIN_TOTAL_EXAMPLES_TO_TRAIN threshold as event_classifier.py
        final_pipeline = train_final_classifier(texts, labels)
        model_path = MODELS_DIR / "event_classifier_tfidf_logreg.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(final_pipeline, f)

        metadata = {
            "method": "tfidf_logreg_v1",
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "n_training_examples": len(texts),
            "class_counts": {c: labels.count(c) for c in sorted(set(labels))},
            "classes": sorted(set(labels)),
            "loocv_evaluation": result["classifier_evaluation"].__dict__ if result["classifier_evaluation"] else None,
            "honest_disclaimer": (
                "DEMO/BASELINE model trained on a small synthetic fixture set "
                f"({len(texts)} examples across {len(set(labels))} classes, several "
                "with only 1-2 examples). NOT production-grade. See README's Phase 3B "
                "section and event_classifier.py's module docstring for full disclosure. "
                "This model is trained on labels that Phase 3A's own keyword heuristic "
                "assigned, not independently verified ground truth."
            ),
        }
        metadata_path = MODELS_DIR / "event_classifier_metadata.json"
        with open(metadata_path, "w") as f:
            jsonlib.dump(metadata, f, indent=2, default=str)

        print(f"  {model_path}  ({model_path.stat().st_size} bytes)")
        print(f"  {metadata_path}")
    else:
        print(f"  Skipped: only {len(texts)} labeled examples (< 6 minimum) -- no model saved, "
              f"consistent with event_classifier.py's MIN_TOTAL_EXAMPLES_TO_TRAIN guard.")

    return result


if __name__ == "__main__":
    main()
