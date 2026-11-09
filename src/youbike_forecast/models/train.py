from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from youbike_forecast.config import settings
from youbike_forecast.models.metrics import regression_metrics
from youbike_forecast.models.splits import expanding_time_folds, final_holdout_mask

FEATURES = [
    "capacity",
    "available_bikes",
    "available_docks",
    "bike_ratio",
    "hour",
    "day_of_week",
    "hour_sin",
    "hour_cos",
    "is_weekend",
    "is_holiday",
    "nearest_mrt_distance_m",
    "neighbor_count_1km",
    "neighbor_bikes_mean",
    "neighbor_bike_ratio_mean",
    "forecast_temperature_2m",
    "forecast_apparent_temperature",
    "forecast_relative_humidity_2m",
    "forecast_precipitation",
    "forecast_precipitation_probability",
    "forecast_weather_code",
    "forecast_wind_speed_10m",
    "forecast_wind_gusts_10m",
    "bikes_lag_5m",
    "bikes_lag_15m",
    "bikes_lag_30m",
    "bikes_lag_60m",
    "bikes_delta_5m",
    "bikes_delta_15m",
    "bikes_delta_30m",
    "bikes_delta_60m",
    "bikes_rolling_mean_60m",
    "bikes_rolling_std_60m",
    "station_code",
    "district_code",
    "source_code",
]


@dataclass(frozen=True)
class Candidate:
    name: str
    factory: Callable[[], object]


def candidates(random_state: int = 42) -> list[Candidate]:
    return [
        Candidate(
            "ridge",
            lambda: make_pipeline(
                SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.0)
            ),
        ),
        Candidate(
            "extra_trees",
            lambda: make_pipeline(
                SimpleImputer(strategy="median"),
                ExtraTreesRegressor(
                    n_estimators=240,
                    min_samples_leaf=3,
                    max_features=0.8,
                    n_jobs=-1,
                    random_state=random_state,
                ),
            ),
        ),
        Candidate(
            "lightgbm",
            lambda: lgb.LGBMRegressor(
                objective="regression_l1",
                n_estimators=500,
                learning_rate=0.04,
                num_leaves=48,
                min_child_samples=80,
                subsample=0.85,
                colsample_bytree=0.85,
                reg_lambda=2.0,
                random_state=random_state,
                n_jobs=-1,
                verbosity=-1,
            ),
        ),
        Candidate(
            "catboost",
            lambda: CatBoostRegressor(
                loss_function="MAE",
                iterations=500,
                depth=8,
                learning_rate=0.05,
                random_seed=random_state,
                verbose=False,
                thread_count=-1,
            ),
        ),
    ]


def prepare_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame["observation_time"] = pd.to_datetime(frame["observation_time"], utc=True)
    for column, code_column in (
        ("station_id", "station_code"),
        ("district", "district_code"),
        ("source", "source_code"),
    ):
        frame[code_column] = pd.Categorical(frame[column]).codes
    return frame.sort_values("observation_time").reset_index(drop=True)


def evaluate_baselines(frame: pd.DataFrame, indices: pd.Index) -> dict[str, dict[str, float]]:
    subset = frame.loc[indices]
    actual = subset["target_bikes"].to_numpy()
    capacity = subset["capacity"].to_numpy()
    trend = subset["available_bikes"] + 2 * (
        subset["available_bikes"] - subset["bikes_lag_30m"].fillna(subset["available_bikes"])
    )
    return {
        "baseline_persistence": regression_metrics(
            actual, subset["available_bikes"].to_numpy(), capacity
        ),
        "baseline_linear_trend": regression_metrics(actual, trend.to_numpy(), capacity),
        "baseline_previous_hour": regression_metrics(
            actual,
            subset["bikes_lag_60m"].fillna(subset["available_bikes"]).to_numpy(),
            capacity,
        ),
    }


def train_and_evaluate(feature_path: Path, output_dir: Path) -> dict[str, object]:
    frame = prepare_frame(feature_path)
    development_mask, holdout_mask = final_holdout_mask(frame["observation_time"], holdout_hours=24)
    development = frame.loc[development_mask].copy()
    holdout = frame.loc[holdout_mask].copy()
    folds = expanding_time_folds(
        development["observation_time"],
        folds=3,
        validation_hours=12,
        purge_minutes=60,
        minimum_train_hours=36,
    )
    cv_results: dict[str, list[dict[str, float]]] = {
        candidate.name: [] for candidate in candidates()
    }
    baseline_results: list[dict[str, dict[str, float]]] = []
    for fold in folds:
        baseline_results.append(evaluate_baselines(development, fold.validation_indices))
        train_frame = development.loc[fold.train_indices]
        validation_frame = development.loc[fold.validation_indices]
        for candidate in candidates():
            model = candidate.factory()
            model.fit(train_frame[FEATURES], train_frame["target_bikes"])
            predictions = model.predict(validation_frame[FEATURES])
            cv_results[candidate.name].append(
                regression_metrics(
                    validation_frame["target_bikes"].to_numpy(),
                    np.asarray(predictions),
                    validation_frame["capacity"].to_numpy(),
                )
            )
    summary = {
        name: {
            metric: float(np.mean([fold_result[metric] for fold_result in fold_results]))
            for metric in fold_results[0]
        }
        for name, fold_results in cv_results.items()
    }
    winner = min(summary, key=lambda name: (summary[name]["mae"], summary[name]["rmse"]))
    selected = next(candidate for candidate in candidates() if candidate.name == winner).factory()
    selected.fit(development[FEATURES], development["target_bikes"])
    holdout_predictions = np.asarray(selected.predict(holdout[FEATURES]))
    final_metrics = regression_metrics(
        holdout["target_bikes"].to_numpy(), holdout_predictions, holdout["capacity"].to_numpy()
    )
    final_baselines = evaluate_baselines(holdout, holdout.index)
    residuals = np.abs(holdout["target_bikes"].to_numpy() - holdout_predictions)
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": selected,
            "features": FEATURES,
            "trained_at": datetime.now(UTC).isoformat(),
            "model_name": winner,
            "conformal_absolute_error_q90": float(np.quantile(residuals, 0.9)),
        },
        output_dir / "model.joblib",
    )
    report: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "winner": winner,
        "selection_rule": "lowest mean CV MAE, then mean CV RMSE",
        "coverage": {
            "start": frame["observation_time"].min().isoformat(),
            "end": frame["observation_time"].max().isoformat(),
            "rows": len(frame),
            "stations": int(frame["station_id"].nunique()),
            "final_holdout_rows": len(holdout),
        },
        "cross_validation": summary,
        "cross_validation_folds": cv_results,
        "baseline_folds": baseline_results,
        "final_holdout": {winner: final_metrics, **final_baselines},
    }
    (output_dir / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run time-aware model competition")
    parser.add_argument(
        "--features",
        type=Path,
        default=settings.data_dir / "features" / "station_hour_ahead.parquet",
    )
    parser.add_argument("--output-dir", type=Path, default=settings.model_dir)
    args = parser.parse_args()
    print(json.dumps(train_and_evaluate(args.features, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
