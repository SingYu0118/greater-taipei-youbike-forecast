from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from youbike_forecast.config import settings
from youbike_forecast.models.metrics import regression_metrics
from youbike_forecast.models.train import (
    FEATURES,
    candidates,
    code_version_from_environment,
    evaluate_baselines,
    prepare_frame,
)


@dataclass(frozen=True)
class EarlyDiagnosticSplit:
    train_indices: pd.Index
    test_indices: pd.Index
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def early_diagnostic_split(
    timestamps: pd.Series,
    *,
    train_window_hours: int = 48,
    test_window_hours: int = 24,
    purge_minutes: int = 60,
) -> EarlyDiagnosticSplit:
    """Create the pre-declared 48-hour train / day-three test diagnostic split."""
    values = pd.to_datetime(timestamps, utc=True)
    earliest = values.min()
    latest = values.max()
    required = timedelta(hours=train_window_hours + test_window_hours)
    if pd.isna(earliest) or pd.isna(latest) or latest - earliest < required:
        observed = 0.0 if pd.isna(earliest) else (latest - earliest).total_seconds() / 3600
        raise ValueError(
            "The 72-hour early diagnostic is not ready: "
            f"observed {observed:.2f} hours; required {required.total_seconds() / 3600:.0f}."
        )

    test_start = earliest + timedelta(hours=train_window_hours)
    train_end = test_start - timedelta(minutes=purge_minutes)
    test_end = test_start + timedelta(hours=test_window_hours)
    train_indices = values[values <= train_end].index
    test_indices = values[(values > test_start) & (values <= test_end)].index
    if not len(train_indices) or not len(test_indices):
        raise ValueError("The early diagnostic split contains an empty train or test period.")
    return EarlyDiagnosticSplit(
        train_indices=train_indices,
        test_indices=test_indices,
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
    )


def run_early_diagnostic(feature_path: Path, output_path: Path) -> dict[str, object]:
    """Evaluate every candidate on day three without publishing a serving artifact."""
    frame, _ = prepare_frame(feature_path)
    split = early_diagnostic_split(frame["observation_time"])
    train_frame = frame.loc[split.train_indices]
    test_frame = frame.loc[split.test_indices]
    model_results: dict[str, dict[str, float]] = {}

    for candidate in candidates():
        model = candidate.factory()
        fit_started = perf_counter()
        model.fit(train_frame[FEATURES], train_frame["target_bikes"])
        fit_seconds = perf_counter() - fit_started
        predict_started = perf_counter()
        predictions = np.asarray(model.predict(test_frame[FEATURES]))
        predict_seconds = perf_counter() - predict_started
        metrics = regression_metrics(
            test_frame["target_bikes"].to_numpy(),
            predictions,
            test_frame["capacity"].to_numpy(),
        )
        model_results[candidate.name] = {
            **metrics,
            "fit_seconds": float(fit_seconds),
            "predict_seconds": float(predict_seconds),
            "prediction_rows_per_second": float(
                len(test_frame) / max(predict_seconds, 1e-9)
            ),
        }

    baselines = evaluate_baselines(test_frame, test_frame.index)
    winner = min(
        model_results,
        key=lambda name: (model_results[name]["mae"], model_results[name]["rmse"]),
    )
    persistence_mae = baselines["baseline_persistence"]["mae"]
    report: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "code_version": code_version_from_environment(),
        "evidence_tier": (
            "official-window preliminary"
            if feature_path.resolve() == settings.formal_feature_path.resolve()
            else "development-only preliminary"
        ),
        "status": "preliminary_not_for_production",
        "protocol": "first 48 hours train, 60-minute purge, third day untouched test",
        "selection_warning": (
            "The day-three ranking is diagnostic only. It does not replace rolling validation "
            "or the five-day publication gate."
        ),
        "coverage": {
            "dataset_start": frame["observation_time"].min().isoformat(),
            "dataset_end": frame["observation_time"].max().isoformat(),
            "train_end": split.train_end.isoformat(),
            "test_start": split.test_start.isoformat(),
            "test_end": split.test_end.isoformat(),
            "train_rows": len(train_frame),
            "test_rows": len(test_frame),
            "stations": int(frame["station_id"].nunique()),
        },
        "winner_on_day_three": winner,
        "models": model_results,
        "baselines": baselines,
        "comparison_to_persistence": {
            "winner_mae": model_results[winner]["mae"],
            "persistence_mae": persistence_mae,
            "mae_improvement_percent": float(
                100 * (persistence_mae - model_results[winner]["mae"]) / max(persistence_mae, 1e-9)
            ),
        },
        "publication_gate": {
            "passed": False,
            "reason": "A 72-hour diagnostic is never a production publication artifact.",
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pre-declared 72-hour early diagnostic")
    parser.add_argument("--features", type=Path, default=settings.formal_feature_path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/preliminary/early-72h-evaluation.json"),
    )
    args = parser.parse_args()
    print(json.dumps(run_early_diagnostic(args.features, args.output), indent=2))


if __name__ == "__main__":
    main()
