import numpy as np
import pandas as pd

from youbike_forecast.models.service import ForecastService
from youbike_forecast.models.train import FEATURES, train_and_evaluate


def test_full_model_competition_writes_final_artifacts(tmp_path) -> None:
    rows = []
    start = pd.Timestamp("2026-11-01", tz="UTC")
    for hour in range(120):
        for station_index in range(2):
            capacity = 30 + station_index * 10
            available = 10 + station_index * 3 + int(4 * np.sin(hour / 5))
            row = {feature: 0.0 for feature in FEATURES}
            row.update(
                {
                    "source": "taipei" if station_index == 0 else "new_taipei",
                    "station_id": f"station-{station_index}",
                    "station_name": f"Station {station_index}",
                    "district": f"district-{station_index}",
                    "latitude": 25.0 + station_index * 0.01,
                    "longitude": 121.5 + station_index * 0.01,
                    "observation_time": start + pd.Timedelta(hour, unit="h"),
                    "capacity": capacity,
                    "available_bikes": available,
                    "available_docks": capacity - available,
                    "bike_ratio": available / capacity,
                    "hour": hour % 24,
                    "day_of_week": (hour // 24) % 7,
                    "hour_sin": np.sin(2 * np.pi * (hour % 24) / 24),
                    "hour_cos": np.cos(2 * np.pi * (hour % 24) / 24),
                    "bikes_lag_5m": available,
                    "bikes_lag_15m": available,
                    "bikes_lag_30m": available - 1,
                    "bikes_lag_60m": available - 1,
                    "bikes_delta_5m": 0,
                    "bikes_delta_15m": 0,
                    "bikes_delta_30m": 1,
                    "bikes_delta_60m": 1,
                    "bikes_rolling_mean_60m": available - 0.5,
                    "bikes_rolling_std_60m": 1.0,
                    "nearest_mrt_distance_m": 250 + station_index * 100,
                    "neighbor_count_1km": 5,
                    "neighbor_bikes_mean": available + 1,
                    "neighbor_bike_ratio_mean": (available + 1) / capacity,
                    "forecast_temperature_2m": 24 + np.sin(hour / 12),
                    "forecast_apparent_temperature": 25 + np.sin(hour / 12),
                    "forecast_relative_humidity_2m": 70,
                    "forecast_precipitation": 1 if hour % 17 == 0 else 0,
                    "forecast_precipitation_probability": 60 if hour % 17 == 0 else 10,
                    "forecast_weather_code": 61 if hour % 17 == 0 else 1,
                    "forecast_wind_speed_10m": 8,
                    "forecast_wind_gusts_10m": 12,
                    "target_bikes": min(capacity, available + 2),
                    "label_is_eligible": True,
                }
            )
            rows.append(row)
    feature_path = tmp_path / "features.parquet"
    pd.DataFrame(rows).to_parquet(feature_path, index=False)
    output = tmp_path / "models"
    report = train_and_evaluate(feature_path, output)
    expected_models = {
        "ridge",
        "random_forest",
        "extra_trees",
        "hist_gradient_boosting",
        "lightgbm",
        "xgboost",
        "catboost",
    }
    assert report["winner"] in expected_models
    assert set(report["cross_validation"]) == {
        *expected_models,
    }
    assert report["coverage"]["final_holdout_rows"] == 48
    assert report["publication_gate"]["passed"] is True
    assert report["model_id"].startswith(f"{report['winner']}-")
    assert set(report["final_holdout_segments"]["source"]) == {"taipei", "new_taipei"}
    assert set(report["final_holdout_segments"]["rain_regime"]) == {"dry", "rain"}
    assert (output / "model.joblib").exists()
    assert (output / "evaluation.json").exists()
    assert (output / "drivers.json").exists()
    service = ForecastService(output, feature_path)
    assert service.is_ready() is True
    assert service.metadata()["model_id"] == report["model_id"]
    forecasts = service.forecasts()
    assert len(forecasts) == 2
    assert forecasts[0]["prediction_low"] <= forecasts[0]["predicted_bikes"]
    snapshot = service.forecast_snapshot()
    assert snapshot["serving_mode"] == "r2-batch-snapshot"
    assert snapshot["count"] == 2
    assert "available_docks" in snapshot["stations"][0]
    assert "dry_prediction" in snapshot["stations"][0]
    assert "heavy_rain_prediction" in snapshot["stations"][0]
    scenario = service.what_if(
        "station-0",
        {"forecast_precipitation": 10.0, "forecast_precipitation_probability": 100.0},
    )
    assert scenario["station_id"] == "station-0"
    assert "difference" in scenario
    gated_service = ForecastService(output, feature_path, tmp_path / "empty-raw")
    assert gated_service.is_ready() is False
