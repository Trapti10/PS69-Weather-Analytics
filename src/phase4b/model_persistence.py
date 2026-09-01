"""
Phase 4B -- model persistence (Part G).

Saves trained models under models/phase4b/{temperature,rainfall}/, each
alongside a JSON metadata file recording enough information to reproduce
and understand the model: model type, target, horizon, feature list,
training date/range, evaluation metrics, preprocessing information, and
random seed. This is a NEW directory -- no earlier phase's model output
(e.g. data/processed/model_temp_rf.pkl from Phase 1's own notebook 05) is
touched or overwritten.
"""
from __future__ import annotations

import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

MODELS_ROOT = Path(__file__).resolve().parents[2] / "models" / "phase4b"


def _target_dir(target: str) -> Path:
    d = MODELS_ROOT / target
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_model(model: Any, target: str, model_name: str, horizon: int,
               feature_cols: List[str], metrics: Dict[str, float],
               train_range: Optional[List[str]] = None,
               preprocessing: str = "Causal lag/rolling features (shift>=1); "
                                     "cyclical hour/day-of-year encodings; dropna() on "
                                     "incomplete rows. See src/phase4b/feature_engineering.py.",
               random_seed: int = 42) -> Path:
    """Saves one fitted model (pickle) + its metadata (JSON) under
    models/phase4b/{target}/{model_name}_h{horizon}.{pkl,json}."""
    d = _target_dir(target)
    stem = f"{model_name}_h{horizon}"
    model_path = d / f"{stem}.pkl"
    meta_path = d / f"{stem}.json"

    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    metadata = {
        "model_type": type(model).__name__,
        "model_name": model_name,
        "target": target,
        "horizon_hours": horizon,
        "feature_list": feature_cols,
        "n_features": len(feature_cols),
        "training_date_utc": datetime.now(timezone.utc).isoformat(),
        "training_data_range": train_range,
        "evaluation_metrics": metrics,
        "preprocessing": preprocessing,
        "random_seed": random_seed,
        "model_file": model_path.name,
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    return model_path


def load_model(target: str, model_name: str, horizon: int):
    """Loads a previously saved model + its metadata. Raises FileNotFoundError
    if the model was never saved -- never returns a fabricated stand-in."""
    d = MODELS_ROOT / target
    stem = f"{model_name}_h{horizon}"
    model_path = d / f"{stem}.pkl"
    meta_path = d / f"{stem}.json"

    if not model_path.exists():
        raise FileNotFoundError(f"No saved Phase 4B model at {model_path}")

    with open(model_path, "rb") as f:
        model = pickle.load(f)
    metadata = None
    if meta_path.exists():
        with open(meta_path, "r") as f:
            metadata = json.load(f)
    return model, metadata
