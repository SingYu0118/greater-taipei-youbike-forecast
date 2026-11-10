from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
from catboost import CatBoostRegressor
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
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


def prepare_frame(path: Path) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    frame = pd.read_parquet(path)
    if "label_is_eligible" in frame:
        frame = frame[frame["label_is_eligible"]].copy()
    if frame.empty:
        raise ValueError("Feature dataset contains no eligible one-hour labels")
    frame["observation_time"] = pd.to_datetime(frame["observation_time"], utc=True)
    frame["station_key"] = frame["source"].astype(str) + ":" + frame["station_id"].astype(str)
    category_maps: dict[str, dict[str, int]] = {}
    for column, code_column in (
        ("station_key", "station_code"),
        ("district", "district_code"),
        ("source", "source_code"),
    ):
        values = sorted(frame[column].fillna("__missing__").astype(str).unique())
        category_maps[column] = {value: index for index, value in enumerate(values)}
        frame[code_column] = (
            frame[column].fillna("__missing__").astype(str).map(category_maps[column])
        )
    return frame.sort_values("observation_time").reset_index(drop=True), category_maps


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


def evaluate_segments(
    holdout: pd.DataFrame, predictions: np.ndarray
) -> dict[str, dict[str, dict[str, float] | int]]:
    scored = holdout.copy()
    scored["prediction"] = predictions
    scored["capacity_band"] = pd.cut(
        scored["capacity"], bins=[-np.inf, 20, 40, np.inf], labels=["small", "medium", "large"]
    ).astype(str)
    scored["rain_regime"] = np.where(scored["forecast_precipitation"] > 0, "rain", "dry")
    scored["day_type"] = np.where(scored["is_weekend"] > 0, "weekend", "weekday")
    scored["risk_class"] = np.select(
        [
            scored["target_bikes"] <= 2,
            scored["target_bikes"] >= scored["capacity"] - 2,
        ],
        ["empty", "full"],
        default="normal",
    )
    dimensions = {
        "source": "source",
        "district": "district",
        "hour": "hour",
        "day_type": "day_type",
        "rain_regime": "rain_regime",
        "capacity_band": "capacity_band",
        "risk_class": "risk_class",
    }
    report: dict[str, dict[str, dict[str, float] | int]] = {}
    for dimension, column in dimensions.items():
        groups: dict[str, dict[str, float] | int] = {}
        for value, group in scored.groupby(column, dropna=False, observed=True):
            groups[str(value)] = {
                "rows": len(group),
                **regression_metrics(
                    group["target_bikes"].to_numpy(),
                    group["prediction"].to_numpy(),
                    group["capacity"].to_numpy(),
                ),
            }
        report[dimension] = groups
    return report


def train_and_evaluate(feature_path: Path, output_dir: Path) -> dict[str, object]:
    frame, category_maps = prepare_frame(feature_path)
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
    cv_absolute_errors: dict[str, list[np.ndarray]] = {
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
            cv_absolute_errors[candidate.name].append(
                np.abs(validation_frame["target_bikes"].to_numpy() - predictions)
            )
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
    segment_metrics = evaluate_segments(holdout, holdout_predictions)
    beats_persistence = (
        final_metrics["mae"] < final_baselines["baseline_persistence"]["mae"]
    )
    calibration_errors = np.concatenate(cv_absolute_errors[winner])
    uncertainty_q90 = float(np.quantile(calibration_errors, 0.9))
    driver_report = explain_model(selected, winner, holdout)
    created_at = datetime.now(UTC)
    model_id = f"{winner}-{created_at:%Y%m%dT%H%M%SZ}"
    code_version = code_version_from_environment()
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": selected,
            "features": FEATURES,
            "trained_at": created_at.isoformat(),
            "model_id": model_id,
            "code_version": code_version,
            "model_name": winner,
            "category_maps": category_maps,
            "conformal_absolute_error_q90": uncertainty_q90,
            "uncertainty_calibration": "rolling_cv_out_of_fold_absolute_residual_q90",
        },
        output_dir / "model.joblib",
    )
    report: dict[str, object] = {
        "created_at": created_at.isoformat(),
        "model_id": model_id,
        "code_version": code_version,
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
        "final_holdout_segments": segment_metrics,
        "publication_gate": {
            "beats_persistence_mae": beats_persistence,
            "passed": beats_persistence,
            "note": "Collection duration and completeness are enforced separately at serving time.",
        },
    }
    (output_dir / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output_dir / "drivers.json").write_text(
        json.dumps(driver_report, indent=2), encoding="utf-8"
    )
    return report


def code_version_from_environment() -> str:
    configured = os.getenv("GIT_COMMIT")
    if configured:
        return configured
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        return "unversioned-local-build"


def explain_model(model: object, model_name: str, holdout: pd.DataFrame) -> dict[str, object]:
    sample = holdout.sample(n=min(len(holdout), 200), random_state=42)
    x_sample = sample[FEATURES]
    permutation = permutation_importance(
        model,
        x_sample,
        sample["target_bikes"],
        scoring="neg_mean_absolute_error",
        n_repeats=3,
        random_state=42,
        n_jobs=1,
    )
    permutation_rows = sorted(
        (
            {
                "feature": feature,
                "importance_mean": float(permutation.importances_mean[index]),
                "importance_std": float(permutation.importances_std[index]),
            }
            for index, feature in enumerate(FEATURES)
        ),
        key=lambda row: abs(row["importance_mean"]),
        reverse=True,
    )
    if model_name in {"ridge", "extra_trees"}:
        transformed = model[:-1].transform(x_sample)  # type: ignore[index]
        estimator = model[-1]  # type: ignore[index]
    else:
        transformed = x_sample
        estimator = model
    if model_name == "ridge":
        explainer = shap.LinearExplainer(estimator, transformed)
        shap_values = np.asarray(explainer.shap_values(transformed))
    else:
        explainer = shap.TreeExplainer(estimator)
        shap_values = np.asarray(explainer.shap_values(transformed))
    mean_absolute = np.mean(np.abs(shap_values), axis=0)
    shap_rows = sorted(
        (
            {"feature": feature, "mean_absolute_shap": float(mean_absolute[index])}
            for index, feature in enumerate(FEATURES)
        ),
        key=lambda row: row["mean_absolute_shap"],
        reverse=True,
    )
    first_values = shap_values[0]
    local_rows = sorted(
        (
            {"feature": feature, "shap_value": float(first_values[index])}
            for index, feature in enumerate(FEATURES)
        ),
        key=lambda row: abs(row["shap_value"]),
        reverse=True,
    )
    return {
        "model": model_name,
        "sample_rows": len(sample),
        "permutation_importance": permutation_rows,
        "global_shap": shap_rows,
        "local_example": {
            "station_id": sample.iloc[0]["station_id"],
            "observation_time": sample.iloc[0]["observation_time"].isoformat(),
            "drivers": local_rows,
        },
        "caution": "SHAP and permutation importance explain model behaviour, not causality.",
    }


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
