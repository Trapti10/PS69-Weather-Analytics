"""
Time-series-aware evaluation utilities.

Critical rule for this project: NEVER randomly shuffle rows before
splitting. All splits below are strictly chronological, so the model
is always evaluated on data that comes after everything it was
trained on.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    precision_score, recall_score, f1_score, roc_auc_score,
)


def chronological_split(df: pd.DataFrame, time_col: str = "valid_time",
                         train_frac: float = 0.7, val_frac: float = 0.15):
    """Split a time-sorted DataFrame into train/val/test chronologically.
    train_frac + val_frac must be < 1; the remainder is the test set."""
    df = df.sort_values(time_col).reset_index(drop=True)
    n = len(df)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]


def regression_report(y_true, y_pred) -> dict:
    return {
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": mean_squared_error(y_true, y_pred) ** 0.5,
        "R2": r2_score(y_true, y_pred),
    }


def classification_report_dict(y_true, y_pred, y_proba=None) -> dict:
    report = {
        "Precision": precision_score(y_true, y_pred, zero_division=0),
        "Recall": recall_score(y_true, y_pred, zero_division=0),
        "F1": f1_score(y_true, y_pred, zero_division=0),
    }
    if y_proba is not None and len(set(y_true)) > 1:
        report["ROC_AUC"] = roc_auc_score(y_true, y_proba)
    return report


def naive_persistence_baseline(df: pd.DataFrame, target_col: str, feature_col: str) -> dict:
    """The simplest possible baseline: predict that the value `horizon`
    hours ahead equals the current value. Any real model must beat this."""
    y_true = df[target_col].values
    y_pred = df[feature_col].values
    return regression_report(y_true, y_pred)
