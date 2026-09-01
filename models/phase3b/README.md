# models/phase3b/ — Saved Event Classifier

## What's here

- `event_classifier_tfidf_logreg.pkl` — a scikit-learn `Pipeline` (TF-IDF vectorizer +
  Logistic Regression), pickled. ~24KB — small by design; no `.gitignore` exclusion needed
  (this is not a downloaded pretrained model, it's trained from scratch on this project's own
  small fixture set — see the honest disclaimer below).
- `event_classifier_metadata.json` — training size, class counts, the LOOCV evaluation that was
  run alongside training, and an explicit disclaimer string.

## How it was trained

`scripts/run_phase3b_demo.py` calls:
```python
texts, labels = build_training_set(all_reports)  # src/intelligence/event_classifier.py
final_pipeline = train_final_classifier(texts, labels)  # fits on ALL available labeled examples
pickle.dump(final_pipeline, open("models/phase3b/event_classifier_tfidf_logreg.pkl", "wb"))
```
Only triggered if at least `MIN_TOTAL_EXAMPLES_TO_TRAIN` (6) labeled examples exist — see
`src/intelligence/event_classifier.py`. The LOOCV evaluation (`evaluate_classifier_leave_one_out`)
is a **separate** run used purely to measure performance; it does not produce this saved file.

## How to load and use it

```python
import pickle

with open("models/phase3b/event_classifier_tfidf_logreg.pkl", "rb") as f:
    pipeline = pickle.load(f)

proba = pipeline.predict_proba(["Heavy rain and flooding near the market area"])[0]
classes = pipeline.named_steps["clf"].classes_
best_class = classes[proba.argmax()]
confidence = proba.max()
```

## Honest disclaimer (also embedded in `event_classifier_metadata.json`)

This is a **DEMO/BASELINE** model trained on ~21 synthetic fixture examples across 8 classes,
several with only 1-2 examples. It is trained to reproduce the labels Phase 3A's own keyword
heuristic assigned — **not** independently verified ground truth. Real-world/out-of-distribution
text (e.g. an event type not in the 8 known classes) will still get a forced prediction among the
8 classes, typically at low confidence (~0.15-0.25) — this is expected given the training size, not
a bug. See `README.md`'s "Phase 3B" section and `src/intelligence/event_classifier.py`'s module
docstring for the full evaluation methodology and results.
