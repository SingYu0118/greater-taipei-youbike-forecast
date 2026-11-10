from datetime import UTC, datetime, timedelta

import polars as pl

from youbike_forecast.features.build import build_features
from youbike_forecast.pipeline.normalize import NORMALIZED_COLUMNS


def test_feature_builder_aligns_one_hour_target(tmp_path) -> None:
    processed = tmp_path / "processed"
    snapshot_dir = processed / "station_snapshots" / "source=taipei"
    snapshot_dir.mkdir(parents=True)
    start = datetime(2026, 11, 9, 0, tzinfo=UTC)
    development_row = {
        "source": "taipei",
        "station_id": "station-1",
        "station_name": "Test station",
        "district": "Test district",
        "address": "Test address",
        "latitude": 25.0,
        "longitude": 121.5,
        "capacity": 20,
        "available_bikes": 1,
        "available_docks": 19,
        "mechanical_bikes": 1,
        "electric_bikes": None,
        "is_active": True,
        "source_updated_at": start - timedelta(hours=1),
        "fetched_at": start - timedelta(hours=1),
    }
    pl.DataFrame([development_row]).select(NORMALIZED_COLUMNS).write_parquet(
        snapshot_dir / "development.parquet"
    )
    for minute, bikes in ((0, 4), (5, 5), (15, 7), (30, 9), (60, 12)):
        observed_at = start + timedelta(minutes=minute)
        row = {
            "source": "taipei",
            "station_id": "station-1",
            "station_name": "Test station",
            "district": "Test district",
            "address": "Test address",
            "latitude": 25.0,
            "longitude": 121.5,
            "capacity": 20,
            "available_bikes": bikes,
            "available_docks": 20 - bikes,
            "mechanical_bikes": bikes,
            "electric_bikes": None,
            "is_active": True,
            "source_updated_at": observed_at,
            "fetched_at": observed_at,
        }
        pl.DataFrame([row]).select(NORMALIZED_COLUMNS).write_parquet(
            snapshot_dir / f"snapshot-{minute:03d}.parquet"
        )
    new_taipei_dir = processed / "station_snapshots" / "source=new_taipei"
    new_taipei_dir.mkdir(parents=True)
    for minute, bikes in ((0, 100), (60, 110)):
        observed_at = start + timedelta(minutes=minute)
        row = {
            "source": "new_taipei",
            "station_id": "station-1",
            "station_name": "Same ID, different city",
            "district": "Other district",
            "address": "Other address",
            "latitude": 25.02,
            "longitude": 121.52,
            "capacity": 200,
            "available_bikes": bikes,
            "available_docks": 200 - bikes,
            "mechanical_bikes": bikes,
            "electric_bikes": 0,
            "is_active": True,
            "source_updated_at": observed_at,
            "fetched_at": observed_at,
        }
        pl.DataFrame([row]).select(NORMALIZED_COLUMNS).write_parquet(
            new_taipei_dir / f"snapshot-{minute:03d}.parquet"
        )
    weather_dir = processed / "weather_forecasts" / "source=weather_forecast"
    weather_dir.mkdir(parents=True)
    pl.DataFrame(
        [
            {
                "grid_id": 0,
                "grid_latitude": 25.0,
                "grid_longitude": 121.5,
                "issued_at": start - timedelta(minutes=5),
                "forecast_time": start + timedelta(hours=1),
                "temperature_2m": 24.0,
                "apparent_temperature": 25.0,
                "relative_humidity_2m": 70,
                "precipitation": 1.0,
                "precipitation_probability": 60,
                "weather_code": 61,
                "wind_speed_10m": 8.0,
                "wind_gusts_10m": 12.0,
            }
        ]
    ).write_parquet(weather_dir / "weather.parquet")
    mrt_path = tmp_path / "mrt.csv"
    mrt_path.write_text(
        "mrt_station_name,latitude,longitude,osm_type,osm_id\n"
        "Test MRT,25.001,121.501,node,1\n",
        encoding="utf-8",
    )
    output = tmp_path / "features.parquet"
    metadata = build_features(processed, output, mrt_path, official_start_at=start)
    frame = pl.read_parquet(output)
    assert metadata["rows"] == 7
    assert metadata["stations"] == 2
    assert metadata["official_start_at"] == start.isoformat()
    eligible = frame.filter(
        pl.col("label_is_eligible") & (pl.col("source") == "taipei")
    )
    assert eligible["target_bikes"].to_list() == [12, 12]
    assert sorted(eligible["target_offset_seconds"].to_list()) == [0.0, 300.0]
    assert frame["nearest_mrt_name"].to_list() == ["Test MRT"] * 7
    assert eligible["forecast_precipitation"].to_list() == [1.0, 1.0]

