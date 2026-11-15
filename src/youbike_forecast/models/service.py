from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from youbike_forecast.pipeline.quality import build_quality_report


class ModelUnavailableError(RuntimeError):
    """Raised when validated model artifacts do not yet exist."""


class ForecastService:
    def __init__(
        self,
        model_dir: Path,
        feature_path: Path,
        raw_root: Path | None = None,
        collector_log_path: Path | None = None,
        official_start_at: datetime | None = None,
    ) -> None:
        self.model_dir = model_dir
        self.feature_path = feature_path
        self.raw_root = raw_root
        self.collector_log_path = collector_log_path
        self.official_start_at = official_start_at
        self._cache_key: tuple[float, float] | None = None
        self._bundle: dict[str, Any] | None = None
        self._latest: pd.DataFrame | None = None

    @property
    def model_path(self) -> Path:
        return self.model_dir / "model.joblib"

    @property
    def evaluation_path(self) -> Path:
        return self.model_dir / "evaluation.json"

    @property
    def drivers_path(self) -> Path:
        return self.model_dir / "drivers.json"

    def is_ready(self) -> bool:
        required = (
            self.model_path,
            self.evaluation_path,
            self.drivers_path,
            self.feature_path,
        )
        if not all(path.exists() for path in required):
            return False
        try:
            evaluation = json.loads(self.evaluation_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        if not evaluation.get("publication_gate", {}).get("passed", False):
            return False
        if self.raw_root is not None:
            quality = build_quality_report(
                self.raw_root, self.collector_log_path, self.official_start_at
            )["minimum_requirement"]
            if not quality["five_days_met"] or not quality["collection_quality_met"]:
                return False
        return True

    def metrics(self) -> dict[str, Any]:
        if not self.evaluation_path.exists():
            raise ModelUnavailableError("Model evaluation is not available yet")
        return json.loads(self.evaluation_path.read_text(encoding="utf-8"))

    def drivers(self) -> dict[str, Any]:
        if not self.drivers_path.exists():
            raise ModelUnavailableError("Model driver report is not available yet")
        return json.loads(self.drivers_path.read_text(encoding="utf-8"))

    def forecasts(self) -> list[dict[str, Any]]:
        return self.forecast_snapshot()["stations"]

    def forecast_snapshot(self) -> dict[str, Any]:
        bundle, latest = self._load()
        predictions = self._predict(bundle, latest)
        dry = latest.copy()
        dry.loc[:, "forecast_precipitation"] = 0.0
        dry.loc[:, "forecast_precipitation_probability"] = 10.0
        heavy_rain = latest.copy()
        heavy_rain.loc[:, "forecast_precipitation"] = 10.0
        heavy_rain.loc[:, "forecast_precipitation_probability"] = 90.0
        dry_predictions = self._predict(bundle, dry)
        heavy_rain_predictions = self._predict(bundle, heavy_rain)
        uncertainty = float(bundle["conformal_absolute_error_q90"])
        output = []
        for position, (_, row) in enumerate(latest.iterrows()):
            prediction = float(np.clip(predictions[position], 0, row["capacity"]))
            dry_prediction = float(np.clip(dry_predictions[position], 0, row["capacity"]))
            heavy_rain_prediction = float(
                np.clip(heavy_rain_predictions[position], 0, row["capacity"])
            )
            output.append(
                {
                    "source": row["source"],
                    "station_id": row["station_id"],
                    "station_name": row["station_name"],
                    "district": row["district"],
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "capacity": int(row["capacity"]),
                    "available_bikes": int(row["available_bikes"]),
                    "available_docks": int(row["available_docks"]),
                    "observation_time": row["observation_time"].isoformat(),
                    "predicted_bikes": round(prediction, 2),
                    "prediction_low": round(max(0.0, prediction - uncertainty), 2),
                    "prediction_high": round(
                        min(float(row["capacity"]), prediction + uncertainty), 2
                    ),
                    "dry_prediction": round(dry_prediction, 2),
                    "heavy_rain_prediction": round(heavy_rain_prediction, 2),
                }
            )
        return {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "as_of": latest["observation_time"].max().isoformat(),
            "count": len(output),
            "model_status": "ready",
            "serving_mode": "r2-batch-snapshot",
            "model": self.metadata(),
            "stations": output,
        }

    def metadata(self) -> dict[str, str]:
        bundle, _ = self._load()
        return {
            "model_id": str(bundle["model_id"]),
            "model_name": str(bundle["model_name"]),
            "trained_at": str(bundle["trained_at"]),
            "code_version": str(bundle["code_version"]),
            "uncertainty_calibration": str(bundle["uncertainty_calibration"]),
        }

    def what_if(
        self, station_id: str, overrides: dict[str, float], source: str | None = None
    ) -> dict[str, Any]:
        bundle, latest = self._load()
        matches = latest[latest["station_id"] == station_id]
        if source is not None:
            matches = matches[matches["source"] == source]
        if matches.empty:
            raise KeyError(station_id)
        baseline_row = matches.iloc[[0]].copy()
        scenario_row = baseline_row.copy()
        for column, value in overrides.items():
            if column not in scenario_row:
                raise ValueError(f"Unsupported scenario field: {column}")
            scenario_row.loc[:, column] = value
        baseline = float(self._predict(bundle, baseline_row)[0])
        scenario = float(self._predict(bundle, scenario_row)[0])
        capacity = float(baseline_row.iloc[0]["capacity"])
        baseline = float(np.clip(baseline, 0, capacity))
        scenario = float(np.clip(scenario, 0, capacity))
        return {
            "station_id": station_id,
            "station_name": baseline_row.iloc[0]["station_name"],
            "observation_time": baseline_row.iloc[0]["observation_time"].isoformat(),
            "baseline_prediction": round(baseline, 2),
            "scenario_prediction": round(scenario, 2),
            "difference": round(scenario - baseline, 2),
            "overrides": overrides,
            "interpretation": "Model response under controlled inputs; not a causal estimate.",
        }

    def _load(self) -> tuple[dict[str, Any], pd.DataFrame]:
        if not self.is_ready():
            raise ModelUnavailableError(
                "Validated model and inference features are not available yet"
            )
        cache_key = (self.model_path.stat().st_mtime, self.feature_path.stat().st_mtime)
        if cache_key != self._cache_key:
            bundle = joblib.load(self.model_path)
            frame = pd.read_parquet(self.feature_path)
            frame["observation_time"] = pd.to_datetime(frame["observation_time"], utc=True)
            latest = (
                frame.sort_values("observation_time")
                .groupby(["source", "station_id"], as_index=False, sort=False)
                .tail(1)
                .reset_index(drop=True)
            )
            latest_time = pd.Timestamp(latest["observation_time"].max())
            freshness_cutoff = latest_time - pd.Timedelta("15min")
            latest = latest.loc[latest["observation_time"] >= freshness_cutoff].reset_index(
                drop=True
            )
            latest["station_key"] = (
                latest["source"].astype(str) + ":" + latest["station_id"].astype(str)
            )
            for column, code_column in (
                ("station_key", "station_code"),
                ("district", "district_code"),
                ("source", "source_code"),
            ):
                mapping = bundle["category_maps"][column]
                latest[code_column] = (
                    latest[column].fillna("__missing__").astype(str).map(mapping).fillna(-1)
                )
            self._bundle = bundle
            self._latest = latest
            self._cache_key = cache_key
        if self._bundle is None or self._latest is None:
            raise ModelUnavailableError("Model cache could not be initialized")
        return self._bundle, self._latest

    @staticmethod
    def _predict(bundle: dict[str, Any], frame: pd.DataFrame) -> np.ndarray:
        features = bundle["features"]
        missing = sorted(set(features) - set(frame.columns))
        if missing:
            raise ValueError(f"Inference features are missing: {', '.join(missing)}")
        return np.asarray(bundle["model"].predict(frame[features]))
