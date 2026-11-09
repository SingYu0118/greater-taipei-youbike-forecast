from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import holidays
import polars as pl

from youbike_forecast.config import settings

FEATURE_SQL = r"""
WITH snapshots AS (
    SELECT
        source,
        station_id,
        station_name,
        district,
        latitude,
        longitude,
        capacity,
        available_bikes,
        available_docks,
        mechanical_bikes,
        electric_bikes,
        is_active,
        fetched_at AS observation_time
    FROM read_parquet($snapshot_glob, union_by_name=true)
),
station_dimension AS (
    SELECT
        station_id,
        LAST(latitude ORDER BY observation_time) AS latitude,
        LAST(longitude ORDER BY observation_time) AS longitude
    FROM snapshots
    GROUP BY station_id
),
neighbor_ranked AS (
    SELECT
        origin.station_id,
        candidate.station_id AS neighbor_station_id,
        SQRT(
            POW((origin.latitude - candidate.latitude) * 111000, 2)
            + POW((origin.longitude - candidate.longitude) * 101000, 2)
        ) AS distance_m,
        ROW_NUMBER() OVER (
            PARTITION BY origin.station_id
            ORDER BY SQRT(
                POW((origin.latitude - candidate.latitude) * 111000, 2)
                + POW((origin.longitude - candidate.longitude) * 101000, 2)
            )
        ) AS neighbor_rank
    FROM station_dimension origin
    JOIN station_dimension candidate ON origin.station_id <> candidate.station_id
    WHERE ABS(origin.latitude - candidate.latitude) < 0.012
      AND ABS(origin.longitude - candidate.longitude) < 0.014
),
neighbor_map AS (
    SELECT * FROM neighbor_ranked WHERE distance_m <= 1000 AND neighbor_rank <= 5
),
neighbor_features AS (
    SELECT
        current.station_id,
        current.observation_time,
        COUNT(neighbor.station_id) AS neighbor_count_1km,
        AVG(neighbor.available_bikes) AS neighbor_bikes_mean,
        AVG(neighbor.available_bikes / NULLIF(neighbor.capacity, 0)::DOUBLE)
            AS neighbor_bike_ratio_mean
    FROM snapshots current
    JOIN neighbor_map mapping ON current.station_id = mapping.station_id
    JOIN snapshots neighbor
      ON neighbor.station_id = mapping.neighbor_station_id
     AND neighbor.observation_time = current.observation_time
    GROUP BY current.station_id, current.observation_time
),
mrt_ranked AS (
    SELECT
        station.station_id,
        mrt.mrt_station_name AS nearest_mrt_name,
        SQRT(
            POW((station.latitude - mrt.latitude) * 111000, 2)
            + POW((station.longitude - mrt.longitude) * 101000, 2)
        ) AS nearest_mrt_distance_m,
        ROW_NUMBER() OVER (
            PARTITION BY station.station_id
            ORDER BY SQRT(
                POW((station.latitude - mrt.latitude) * 111000, 2)
                + POW((station.longitude - mrt.longitude) * 101000, 2)
            )
        ) AS mrt_rank
    FROM station_dimension station
    CROSS JOIN read_csv_auto($mrt_path, header=true) mrt
),
nearest_mrt AS (
    SELECT station_id, nearest_mrt_name, nearest_mrt_distance_m
    FROM mrt_ranked WHERE mrt_rank = 1
),
weather_grids AS (
    SELECT DISTINCT grid_id, grid_latitude, grid_longitude
    FROM read_parquet($weather_glob, union_by_name=true)
),
weather_grid_ranked AS (
    SELECT
        station.station_id,
        weather.grid_id,
        ROW_NUMBER() OVER (
            PARTITION BY station.station_id
            ORDER BY SQRT(
                POW((station.latitude - weather.grid_latitude) * 111000, 2)
                + POW((station.longitude - weather.grid_longitude) * 101000, 2)
            )
        ) AS weather_rank
    FROM station_dimension station
    CROSS JOIN weather_grids weather
),
station_weather_grid AS (
    SELECT station_id, grid_id FROM weather_grid_ranked WHERE weather_rank = 1
),
base AS (
    SELECT
        snapshot.*,
        EXTRACT(hour FROM snapshot.observation_time AT TIME ZONE 'Asia/Taipei')::INTEGER AS hour,
        EXTRACT(dow FROM snapshot.observation_time AT TIME ZONE 'Asia/Taipei')::INTEGER
            AS day_of_week,
        SIN(
            2 * PI()
            * EXTRACT(hour FROM snapshot.observation_time AT TIME ZONE 'Asia/Taipei')
            / 24.0
        ) AS hour_sin,
        COS(
            2 * PI()
            * EXTRACT(hour FROM snapshot.observation_time AT TIME ZONE 'Asia/Taipei')
            / 24.0
        ) AS hour_cos,
        snapshot.available_bikes / NULLIF(snapshot.capacity, 0)::DOUBLE AS bike_ratio,
        AVG(snapshot.available_bikes) OVER station_window AS bikes_rolling_mean_60m,
        STDDEV_POP(snapshot.available_bikes) OVER station_window AS bikes_rolling_std_60m,
        COALESCE(calendar.is_holiday, false)::INTEGER AS is_holiday,
        calendar.holiday_name,
        mrt.nearest_mrt_name,
        mrt.nearest_mrt_distance_m,
        COALESCE(neighbor.neighbor_count_1km, 0) AS neighbor_count_1km,
        neighbor.neighbor_bikes_mean,
        neighbor.neighbor_bike_ratio_mean,
        weather_grid.grid_id,
        DATE_TRUNC('hour', snapshot.observation_time + INTERVAL 90 MINUTE)
            AS target_weather_hour
    FROM snapshots snapshot
    LEFT JOIN read_parquet($calendar_path) calendar
      ON CAST(snapshot.observation_time AT TIME ZONE 'Asia/Taipei' AS DATE) = calendar.date
    LEFT JOIN nearest_mrt mrt ON snapshot.station_id = mrt.station_id
    LEFT JOIN neighbor_features neighbor
      ON snapshot.station_id = neighbor.station_id
     AND snapshot.observation_time = neighbor.observation_time
    LEFT JOIN station_weather_grid weather_grid
      ON snapshot.station_id = weather_grid.station_id
    WINDOW station_window AS (
        PARTITION BY snapshot.station_id ORDER BY epoch(snapshot.observation_time)
        RANGE BETWEEN 3600 PRECEDING AND CURRENT ROW
    )
),
weather_augmented AS (
    SELECT
        base.*,
        weather.issued_at AS weather_issued_at,
        weather.temperature_2m AS forecast_temperature_2m,
        weather.apparent_temperature AS forecast_apparent_temperature,
        weather.relative_humidity_2m AS forecast_relative_humidity_2m,
        weather.precipitation AS forecast_precipitation,
        weather.precipitation_probability AS forecast_precipitation_probability,
        weather.weather_code AS forecast_weather_code,
        weather.wind_speed_10m AS forecast_wind_speed_10m,
        weather.wind_gusts_10m AS forecast_wind_gusts_10m
    FROM base
    ASOF LEFT JOIN read_parquet($weather_glob, union_by_name=true) weather
      ON base.grid_id = weather.grid_id
     AND base.target_weather_hour = weather.forecast_time
     AND weather.issued_at <= base.observation_time
),
lagged AS (
    SELECT
        current.*,
        lag5.available_bikes AS bikes_lag_5m,
        lag15.available_bikes AS bikes_lag_15m,
        lag30.available_bikes AS bikes_lag_30m,
        lag60.available_bikes AS bikes_lag_60m
    FROM weather_augmented current
    ASOF LEFT JOIN base lag5
        ON current.station_id = lag5.station_id
        AND lag5.observation_time <= current.observation_time - INTERVAL 5 MINUTE
    ASOF LEFT JOIN base lag15
        ON current.station_id = lag15.station_id
        AND lag15.observation_time <= current.observation_time - INTERVAL 15 MINUTE
    ASOF LEFT JOIN base lag30
        ON current.station_id = lag30.station_id
        AND lag30.observation_time <= current.observation_time - INTERVAL 30 MINUTE
    ASOF LEFT JOIN base lag60
        ON current.station_id = lag60.station_id
        AND lag60.observation_time <= current.observation_time - INTERVAL 60 MINUTE
),
labeled AS (
    SELECT
        lagged.*,
        future.available_bikes AS target_bikes,
        future.available_docks AS target_docks,
        future.observation_time AS target_observed_at,
        ABS(epoch(future.observation_time) - epoch(lagged.observation_time + INTERVAL 60 MINUTE))
            AS target_offset_seconds
    FROM lagged
    ASOF LEFT JOIN base future
        ON lagged.station_id = future.station_id
        AND future.observation_time >= lagged.observation_time + INTERVAL 53 MINUTE
)
SELECT
    *,
    available_bikes - bikes_lag_5m AS bikes_delta_5m,
    available_bikes - bikes_lag_15m AS bikes_delta_15m,
    available_bikes - bikes_lag_30m AS bikes_delta_30m,
    available_bikes - bikes_lag_60m AS bikes_delta_60m,
    CASE WHEN day_of_week IN (0, 6) THEN 1 ELSE 0 END AS is_weekend,
    CASE WHEN target_bikes <= 2 THEN 1 ELSE 0 END AS target_empty_risk,
    CASE WHEN target_docks <= 2 THEN 1 ELSE 0 END AS target_full_risk
FROM labeled
WHERE target_bikes IS NOT NULL
  AND target_offset_seconds <= 420
  AND is_active
  AND capacity > 0
"""


def build_features(
    processed_dir: Path,
    output_path: Path,
    mrt_path: Path = Path("data/reference/greater_taipei_mrt_stations.csv"),
) -> dict[str, object]:
    station_root = processed_dir / "station_snapshots"
    weather_root = processed_dir / "weather_forecasts"
    station_files = list(station_root.glob("**/*.parquet"))
    weather_files = list(weather_root.glob("**/*.parquet"))
    if not station_files:
        raise FileNotFoundError(f"No station Parquet shards found under {processed_dir}")
    if not weather_files:
        raise FileNotFoundError(f"No weather Parquet shards found under {processed_dir}")
    if not mrt_path.exists():
        raise FileNotFoundError(f"MRT reference file not found: {mrt_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".parquet.tmp")
    calendar_path = output_path.parent / "taiwan_calendar.parquet"
    snapshot_glob = str(station_root / "**" / "*.parquet")
    weather_glob = str(weather_root / "**" / "*.parquet")
    connection = duckdb.connect()
    connection.execute("SET TimeZone='UTC'")
    coverage = connection.execute(
        "SELECT MIN(fetched_at), MAX(fetched_at) FROM read_parquet(?)", [snapshot_glob]
    ).fetchone()
    _write_calendar(calendar_path, coverage[0].date(), coverage[1].date())
    parameters = {
        "snapshot_glob": snapshot_glob,
        "weather_glob": weather_glob,
        "mrt_path": str(mrt_path),
        "calendar_path": str(calendar_path),
    }
    connection.execute(
        f"COPY ({FEATURE_SQL}) TO '{temporary_path}' (FORMAT PARQUET, COMPRESSION ZSTD)",
        parameters,
    )
    row_count = connection.execute(
        "SELECT COUNT(*) FROM read_parquet(?)", [str(temporary_path)]
    ).fetchone()[0]
    feature_coverage = connection.execute(
        "SELECT MIN(observation_time), MAX(observation_time), COUNT(DISTINCT station_id) "
        "FROM read_parquet(?)",
        [str(temporary_path)],
    ).fetchone()
    connection.close()
    temporary_path.replace(output_path)
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "output": str(output_path),
        "rows": row_count,
        "stations": feature_coverage[2],
        "observation_start": (
            feature_coverage[0].isoformat() if feature_coverage[0] else None
        ),
        "observation_end": feature_coverage[1].isoformat() if feature_coverage[1] else None,
    }


def _write_calendar(output: Path, start: date, end: date) -> None:
    taiwan_holidays = holidays.country_holidays(
        "TW", years=range(start.year, end.year + 1), language="en_US"
    )
    rows = []
    current = start
    while current <= end:
        rows.append(
            {
                "date": current,
                "is_holiday": current in taiwan_holidays,
                "holiday_name": taiwan_holidays.get(current),
            }
        )
        current += timedelta(days=1)
    pl.DataFrame(rows).write_parquet(output, compression="zstd")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build leakage-safe one-hour forecast features")
    parser.add_argument("--processed-dir", type=Path, default=settings.processed_dir)
    parser.add_argument(
        "--output", type=Path, default=settings.data_dir / "features" / "station_hour_ahead.parquet"
    )
    parser.add_argument(
        "--mrt-reference",
        type=Path,
        default=settings.data_dir / "reference" / "greater_taipei_mrt_stations.csv",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            build_features(args.processed_dir, args.output, args.mrt_reference), indent=2
        )
    )


if __name__ == "__main__":
    main()
