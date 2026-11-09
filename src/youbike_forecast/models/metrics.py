from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error


def regression_metrics(
    actual: np.ndarray, predicted: np.ndarray, capacity: np.ndarray
) -> dict[str, float]:
    predicted = np.clip(predicted, 0, capacity)
    absolute_error = np.abs(actual - predicted)
    empty_actual = actual <= 2
    empty_predicted = predicted <= 2
    full_actual = actual >= (capacity - 2)
    full_predicted = predicted >= (capacity - 2)
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "wape": float(absolute_error.sum() / max(np.abs(actual).sum(), 1.0)),
        "empty_recall": _recall(empty_actual, empty_predicted),
        "full_recall": _recall(full_actual, full_predicted),
    }


def _recall(actual: np.ndarray, predicted: np.ndarray) -> float:
    positives = int(actual.sum())
    if positives == 0:
        return 0.0
    return float(np.logical_and(actual, predicted).sum() / positives)

