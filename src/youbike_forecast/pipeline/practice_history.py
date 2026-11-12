from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import polars as pl

from youbike_forecast.features.build import build_features

REPOSITORY_URL = "https://github.com/tses89214/youbike-historical-data"
RAW_BASE_URL = (
    "https://raw.githubusercontent.com/tses89214/youbike-historical-data/main/data"
)
LICENSE_URL = f"{REPOSITORY_URL}/blob/main/LICENSE"
DEFAULT_START = date(2025, 6, 19)
DEFAULT_END = date(2025, 6, 22)
DEFAULT_SITES_DATE = date(2025, 6, 22)

NORMALIZED_COLUMNS = [
    "source",
    "station_id",
    "station_name",
    "district",
    "address",
    "latitude",
    "longitude",
    "capacity",
    "available_bikes",
    "available_docks",
    "mechanical_bikes",
    "electric_bikes",
    "is_active",
    "source_updated_at",
    "fetched_at",
]


def _dates(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end date must be on or after start date")
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def download_practice_history(
    output_dir: Path,
    start: date,
    end: date,
    sites_date: date = DEFAULT_SITES_DATE,
    base_url: str = RAW_BASE_URL,
) -> dict[str, object]:
    """Download only the requested public CSV files, not the multi-gigabyte repository."""
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[str] = []
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        requests = [("sites", sites_date)] + [("slots", day) for day in _dates(start, end)]
        for kind, day in requests:
            destination = output_dir / kind / f"{day.isoformat()}.csv"
            if destination.exists() and destination.stat().st_size:
                downloaded.append(str(destination))
                continue
            response = client.get(f"{base_url}/{kind}/{day.isoformat()}.csv")
            response.raise_for_status()
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(".csv.tmp")
            temporary.write_bytes(response.content)
            temporary.replace(destination)
            downloaded.append(str(destination))
    manifest = {
        "purpose": "development-only model and pipeline practice",
        "repository": REPOSITORY_URL,
        "license": LICENSE_URL,
        "coverage_requested": {"start": start.isoformat(), "end": end.isoformat()},
        "sites_date": sites_date.isoformat(),
        "downloaded_files": downloaded,
        "formal_evidence_eligible": False,
    }
    (output_dir / "download-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def _station_sample(station_ids: list[str], limit: int | None) -> list[str]:
    unique = sorted(set(station_ids))
    if limit is None or limit >= len(unique):
        return unique
    if limit < 1:
        raise ValueError("station limit must be at least one")
    if limit == 1:
        return [unique[len(unique) // 2]]
    indices = [round(index * (len(unique) - 1) / (limit - 1)) for index in range(limit)]
    return [unique[index] for index in indices]


def build_practice_parquet(
    download_dir: Path,
    processed_dir: Path,
    start: date,
    end: date,
    sites_date: date = DEFAULT_SITES_DATE,
    station_limit: int | None = 300,
) -> dict[str, object]:
    """Convert third-party history to a physically separate development-only dataset."""
    sites_path = download_dir / "sites" / f"{sites_date.isoformat()}.csv"
    if not sites_path.exists():
        raise FileNotFoundError(f"Missing station dimension: {sites_path}")
    sites = pl.read_csv(sites_path, infer_schema_length=10_000).with_columns(
        pl.col("sno").cast(pl.String)
    )
    selected = _station_sample(sites.get_column("sno").to_list(), station_limit)
    sites = sites.filter(pl.col("sno").is_in(selected))

    totals = {"input_rows": 0, "written_rows": 0, "dropped_rows": 0, "files": 0}
    minimum_time: datetime | None = None
    maximum_time: datetime | None = None
    for day in _dates(start, end):
        slots_path = download_dir / "slots" / f"{day.isoformat()}.csv"
        if not slots_path.exists():
            raise FileNotFoundError(f"Missing inventory history: {slots_path}")
        slots = pl.read_csv(slots_path, infer_schema_length=10_000).with_columns(
            pl.col("sno").cast(pl.String)
        )
        totals["input_rows"] += slots.height
        joined = slots.join(sites, on="sno", how="inner")
        observation_time = (
            pl.col("infoTime")
            .str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S", strict=True)
            .dt.replace_time_zone("Asia/Taipei")
            .dt.convert_time_zone("UTC")
        )
        normalized = (
            joined.select(
                pl.lit("taipei").alias("source"),
                pl.col("sno").alias("station_id"),
                pl.col("sna").str.replace(r"^YouBike2\.0_", "").alias("station_name"),
                pl.col("sarea").alias("district"),
                pl.col("ar").alias("address"),
                pl.col("latitude").cast(pl.Float64),
                pl.col("longitude").cast(pl.Float64),
                pl.col("total").cast(pl.Int64).alias("capacity"),
                pl.col("available_rent_bikes").cast(pl.Int64).alias("available_bikes"),
                pl.col("available_return_bikes").cast(pl.Int64).alias("available_docks"),
                pl.col("available_rent_bikes").cast(pl.Int64).alias("mechanical_bikes"),
                pl.lit(None, dtype=pl.Int64).alias("electric_bikes"),
                (pl.col("act").cast(pl.String) == "1").alias("is_active"),
                observation_time.alias("source_updated_at"),
                observation_time.alias("fetched_at"),
            )
            .unique(subset=["station_id", "fetched_at"], keep="last")
            .filter(
                pl.col("capacity").is_not_null()
                & pl.col("available_bikes").is_not_null()
                & pl.col("available_docks").is_not_null()
                & (pl.col("capacity") > 0)
                & (pl.col("available_bikes") >= 0)
                & (pl.col("available_docks") >= 0)
                & (pl.col("available_bikes") <= pl.col("capacity"))
            )
            .select(NORMALIZED_COLUMNS)
            .sort(["fetched_at", "station_id"])
        )
        totals["dropped_rows"] += joined.height - normalized.height
        totals["written_rows"] += normalized.height
        totals["files"] += 1
        if normalized.height:
            day_min = normalized.get_column("fetched_at").min()
            day_max = normalized.get_column("fetched_at").max()
            minimum_time = day_min if minimum_time is None else min(minimum_time, day_min)
            maximum_time = day_max if maximum_time is None else max(maximum_time, day_max)
        output = (
            processed_dir
            / "station_snapshots"
            / "source=taipei"
            / f"date={day.isoformat()}"
            / "practice-history.parquet"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        normalized.write_parquet(output, compression="zstd", statistics=True)

    if minimum_time is None or maximum_time is None:
        raise ValueError("Practice history produced no valid normalized rows")
    _write_placeholder_weather(processed_dir, minimum_time, maximum_time)
    report = {
        **totals,
        "stations": len(selected),
        "observation_start": minimum_time.isoformat(),
        "observation_end": maximum_time.isoformat(),
        "timestamp_semantics": (
            "fetched_at uses the publisher's infoTime because the third-party CSV does not "
            "retain collector fetch timestamps"
        ),
        "weather_semantics": (
            "all weather predictors use constant zero placeholders and contain no weather signal"
        ),
        "formal_evidence_eligible": False,
    }
    manifest_dir = processed_dir / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "practice-history.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def _write_placeholder_weather(processed_dir: Path, start: datetime, end: datetime) -> None:
    first_hour = start.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    final_hour = end.astimezone(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(
        hours=2
    )
    grids = [(0, 25.0375, 121.5637), (1, 25.0120, 121.4650), (2, 25.0200, 121.7000)]
    rows: list[dict[str, object]] = []
    current = first_hour
    while current <= final_hour:
        for grid_id, latitude, longitude in grids:
            rows.append(
                {
                    "grid_id": grid_id,
                    "grid_latitude": latitude,
                    "grid_longitude": longitude,
                    "issued_at": current - timedelta(hours=2),
                    "forecast_time": current,
                    "temperature_2m": 0.0,
                    "apparent_temperature": 0.0,
                    "relative_humidity_2m": 0.0,
                    "precipitation": 0.0,
                    "precipitation_probability": 0.0,
                    "weather_code": 0.0,
                    "wind_speed_10m": 0.0,
                    "wind_gusts_10m": 0.0,
                }
            )
        current += timedelta(hours=1)
    schema = {
        "grid_id": pl.Int64,
        "grid_latitude": pl.Float64,
        "grid_longitude": pl.Float64,
        "issued_at": pl.Datetime(time_zone="UTC"),
        "forecast_time": pl.Datetime(time_zone="UTC"),
        "temperature_2m": pl.Float64,
        "apparent_temperature": pl.Float64,
        "relative_humidity_2m": pl.Float64,
        "precipitation": pl.Float64,
        "precipitation_probability": pl.Float64,
        "weather_code": pl.Float64,
        "wind_speed_10m": pl.Float64,
        "wind_gusts_10m": pl.Float64,
    }
    output = processed_dir / "weather_forecasts" / "practice-null-weather.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows, schema=schema).write_parquet(output, compression="zstd")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and build a development-only Taipei YouBike history dataset"
    )
    parser.add_argument("--start-date", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end-date", type=date.fromisoformat, default=DEFAULT_END)
    parser.add_argument("--sites-date", type=date.fromisoformat, default=DEFAULT_SITES_DATE)
    parser.add_argument("--stations", type=int, default=300)
    parser.add_argument(
        "--download-dir", type=Path, default=Path("data/practice_downloads/tses89214")
    )
    parser.add_argument(
        "--processed-dir", type=Path, default=Path("data/practice_processed")
    )
    parser.add_argument(
        "--features", type=Path, default=Path("data/practice_features/station_hour_ahead.parquet")
    )
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()
    download_report = None
    if not args.skip_download:
        download_report = download_practice_history(
            args.download_dir, args.start_date, args.end_date, args.sites_date
        )
    dataset_report = build_practice_parquet(
        args.download_dir,
        args.processed_dir,
        args.start_date,
        args.end_date,
        args.sites_date,
        args.stations,
    )
    feature_report = build_features(
        args.processed_dir,
        args.features,
        official_start_at=None,
    )
    print(
        json.dumps(
            {
                "purpose": "development-only practice; never formal evidence",
                "download": download_report,
                "dataset": dataset_report,
                "features": feature_report,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
