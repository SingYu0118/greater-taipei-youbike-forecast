from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd


@dataclass(frozen=True)
class TimeFold:
    train_indices: pd.Index
    validation_indices: pd.Index
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp


def expanding_time_folds(
    timestamps: pd.Series,
    *,
    folds: int = 3,
    validation_hours: int = 12,
    purge_minutes: int = 60,
    minimum_train_hours: int = 36,
) -> list[TimeFold]:
    """Create expanding folds using whole timestamps and a leakage-preventing purge gap."""
    values = pd.to_datetime(timestamps, utc=True)
    earliest = values.min()
    latest = values.max()
    validation_window = timedelta(hours=validation_hours)
    purge = timedelta(minutes=purge_minutes)
    first_validation_start = latest - (folds * validation_window)
    results: list[TimeFold] = []
    for fold_number in range(folds):
        validation_start = first_validation_start + (fold_number * validation_window)
        validation_end = validation_start + validation_window
        train_end = validation_start - purge
        if train_end - earliest < timedelta(hours=minimum_train_hours):
            continue
        train_indices = values[values <= train_end].index
        validation_indices = values[
            (values > validation_start) & (values <= validation_end)
        ].index
        if len(train_indices) and len(validation_indices):
            results.append(
                TimeFold(
                    train_indices=train_indices,
                    validation_indices=validation_indices,
                    train_end=train_end,
                    validation_start=validation_start,
                    validation_end=validation_end,
                )
            )
    if len(results) < 2:
        raise ValueError("Not enough time coverage to create at least two valid expanding folds")
    return results


def final_holdout_mask(
    timestamps: pd.Series, holdout_hours: int = 24
) -> tuple[pd.Series, pd.Series]:
    values = pd.to_datetime(timestamps, utc=True)
    cutoff = values.max() - timedelta(hours=holdout_hours)
    return values <= cutoff, values > cutoff

