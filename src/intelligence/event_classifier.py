"""
Weather event-type classifier for WeatherReport objects (Phase 3B).

*** WHAT THIS REPLACES/AUGMENTS ***
Phase 3A's `social_report_adapter.infer_event_type_from_text()` is an
ordered, transparent KEYWORD heuristic (not ML) -- ground truth for report
text that happens to contain one of a fixed list of substrings, and it is
what populates the `event_type` field reports already carry. This module
adds a genuine ML classifier (TF-IDF + Logistic Regression) trained on the
SAME labels the keyword heuristic already assigned, and stores its own
prediction in the NEW `predicted_event_category` /
`event_classification_confidence` fields -- it does not overwrite
`event_type`. This is a deliberate choice: overwriting a human-legible
rule-based field with an ML guess, silently, would hide provenance. Both
are kept, clearly labeled by `classification_method`.

*** HONEST SAMPLE-SIZE DISCLOSURE -- READ BEFORE TRUSTING ANY METRIC HERE ***
As of this phase, the ENTIRE labeled corpus (valid, non-empty-text reports
across both fixtures) is on the order of ~20 examples across ~7-8 classes,
several with only 2-3 examples. This is genuinely too small for a
production classifier and too small for a single held-out test split to be
statistically meaningful (a handful of examples can flip accuracy by 10+
points). The honest evaluation choice here is LEAVE-ONE-OUT CROSS-VALIDATION
(every example gets used as the sole test case exactly once, against a
model trained on all the others) -- not because it produces a bigger or
more flattering number, but because with this few examples per class, a
single fixed train/test split would be dominated by which few examples
happened to land in "test." All metrics from this module MUST be reported
as DEMO/BASELINE, never as production accuracy, per this project's explicit
instructions. See report_intelligence.py / README's "Phase 3B" section for
the actual numbers from the actual run -- not invented here.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from sklearn.pipeline import Pipeline

sys.path.append(str(Path(__file__).resolve().parents[1]))
from schemas.weather_report import WeatherReport, EVENT_TYPES
from ingestion.report_normalizer import normalize_text

CLASSIFICATION_METHOD = "tfidf_logreg_v1"
CLASSIFICATION_METHOD_FALLBACK = "keyword_heuristic_fallback"

MIN_TEXT_LENGTH_FOR_CLASSIFICATION = 3
# Below this many labeled examples total, training is refused outright
# (not just "low confidence") -- there's a difference between a weak model
# and no model.
MIN_TOTAL_EXAMPLES_TO_TRAIN = 6


def _build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, stop_words="english")),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])


def build_training_set(reports: List[WeatherReport]) -> Tuple[List[str], List[str]]:
    """Extract (text, label) pairs usable for training: valid reports (not
    REJECTED), with real text, and a known event_type (i.e. what Phase 3A's
    keyword heuristic already assigned -- this classifier is trained to
    reproduce/generalize that labeling, not against some other ground truth
    that doesn't exist in this project)."""
    texts, labels = [], []
    for r in reports:
        if r.verification_status == "REJECTED":
            continue
        text = normalize_text(r.text) or ""
        if len(text) < MIN_TEXT_LENGTH_FOR_CLASSIFICATION:
            continue
        if r.event_type not in EVENT_TYPES:
            continue
        texts.append(text)
        labels.append(r.event_type)
    return texts, labels


@dataclass
class ClassifierEvaluation:
    method: str
    n_examples: int
    class_counts: Dict[str, int]
    accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    confusion_matrix: List[List[int]]
    confusion_matrix_labels: List[str]
    warning: str


def evaluate_classifier_leave_one_out(texts: List[str], labels: List[str]) -> ClassifierEvaluation:
    """Leave-one-out cross-validated evaluation -- see module docstring for
    why LOOCV is the honest choice at this sample size. Returns metrics
    labeled DEMO/BASELINE; callers must not present these as production
    accuracy (enforced by report_intelligence.py's output labeling, not by
    this function alone)."""
    class_counts = {c: labels.count(c) for c in sorted(set(labels))}
    n = len(texts)

    pipeline = _build_pipeline()
    loo = LeaveOneOut()
    y_true, y_pred = [], []

    for train_idx, test_idx in loo.split(texts):
        X_train = [texts[i] for i in train_idx]
        y_train = [labels[i] for i in train_idx]
        X_test = [texts[i] for i in test_idx]
        y_test = [labels[i] for i in test_idx]

        # A class that appears only in the held-out example (impossible for
        # the model to have ever seen) cannot be predicted correctly by
        # construction -- this is expected at this sample size, not a bug,
        # and is exactly the kind of thing LOOCV honestly exposes rather
        # than hides.
        try:
            pipeline.fit(X_train, y_train)
            pred = pipeline.predict(X_test)
        except ValueError:
            pred = ["OTHER"]  # degenerate fit (e.g. single-class training fold)

        y_true.extend(y_test)
        y_pred.extend(pred)

    labels_sorted = sorted(set(y_true) | set(y_pred))
    acc = accuracy_score(y_true, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels_sorted, average="macro", zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=labels_sorted)

    warning = (
        f"DEMO/BASELINE ONLY -- {n} total labeled examples across "
        f"{len(class_counts)} classes (min class count: {min(class_counts.values())}). "
        f"This is too small for production-grade evaluation; leave-one-out "
        f"cross-validation was used because a single fixed train/test split "
        f"would be dominated by which few examples happened to land in "
        f"'test'. Not representative of real-world accuracy."
    )

    return ClassifierEvaluation(
        method=CLASSIFICATION_METHOD,
        n_examples=n,
        class_counts=class_counts,
        accuracy=round(float(acc), 4),
        precision_macro=round(float(prec), 4),
        recall_macro=round(float(rec), 4),
        f1_macro=round(float(f1), 4),
        confusion_matrix=cm.tolist(),
        confusion_matrix_labels=labels_sorted,
        warning=warning,
    )


def train_final_classifier(texts: List[str], labels: List[str]) -> Pipeline:
    """Train on ALL available labeled examples (for actually generating
    predictions on new/unlabeled reports) -- separate from the LOOCV
    evaluation above, which exists purely to measure performance, not to
    produce the deployed model."""
    pipeline = _build_pipeline()
    pipeline.fit(texts, labels)
    return pipeline


def classify_reports(reports: List[WeatherReport], pipeline: Pipeline = None,
                      training_texts: List[str] = None, training_labels: List[str] = None) -> List[WeatherReport]:
    """Predict predicted_event_category / event_classification_confidence
    for every report with usable text. Reports with too little text to
    classify keep these fields as None (honestly unassessed) and fall back
    to their existing Phase 3A keyword-heuristic event_type, with
    classification_method explicitly set to the fallback label -- never
    silently presented as an ML prediction."""
    if pipeline is None:
        if training_texts is None or training_labels is None:
            raise ValueError("Must provide either a fitted pipeline or training_texts+training_labels.")
        if len(training_texts) < MIN_TOTAL_EXAMPLES_TO_TRAIN:
            for r in reports:
                r.predicted_event_category = None
                r.event_classification_confidence = None
                r.classification_method = CLASSIFICATION_METHOD_FALLBACK
            return reports
        pipeline = train_final_classifier(training_texts, training_labels)

    classes = [str(c) for c in pipeline.named_steps["clf"].classes_]

    for r in reports:
        text = normalize_text(r.text) or ""
        if len(text) < MIN_TEXT_LENGTH_FOR_CLASSIFICATION:
            r.predicted_event_category = None
            r.event_classification_confidence = None
            r.classification_method = CLASSIFICATION_METHOD_FALLBACK
            continue

        proba = pipeline.predict_proba([text])[0]
        best_idx = int(np.argmax(proba))
        r.predicted_event_category = classes[best_idx]
        r.event_classification_confidence = round(float(proba[best_idx]), 4)
        r.classification_method = CLASSIFICATION_METHOD

    return reports
