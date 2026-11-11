from __future__ import annotations

import argparse
import gzip
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from youbike_forecast.config import settings
from youbike_forecast.pipeline.normalize import (
    normalize_new_taipei,
    normalize_taipei,
    validate_snapshot,
)

TIMESTAMP_PATTERN = re.compile(r"(\d{8}T\d{6}(?:\.\d+)?Z)-[a-f0-9]{12}\.json\.gz$")


def timestamp_from_path(path: Path) -> datetime:
    match = TIMESTAMP_PATTERN.search(path.name)
    if not match:
        raise ValueError(f"Cannot extract fetch timestamp from {path}")
    timestamp = match.group(1)
    pattern = "%Y%m%dT%H%M%S.%fZ" if "." in timestamp else "%Y%m%dT%H%M%SZ"
    return datetime.strptime(timestamp, pattern).replace(tzinfo=UTC)


def read_gzip_json(path: Path) -> object:
    with gzip.open(path, "rt", encoding="utf-8") as source_file:
        return json.load(source_file)


def build_station_parquet(raw_root: Path, processed_root: Path) -> dict[str, int]:
    """Convert every immutable raw station object into a stable one-to-one Parquet shard."""
    totals = {"raw_files": 0, "written_files": 0, "skipped_files": 0, "rows": 0}
    for source, normalizer in (
        ("taipei", normalize_taipei),
        ("new_taipei", normalize_new_taipei),
    ):
        source_root = raw_root / f"source={source}"
        for raw_path in sorted(source_root.glob("date=*/hour=*/*.json.gz")):
            totals["raw_files"] += 1
            relative = raw_path.relative_to(raw_root)
            output_path = (
                (processed_root / "station_snapshots" / relative)
                .with_suffix("")
                .with_suffix(".parquet")
            )
            if output_path.exists():
                totals["skipped_files"] += 1
                continue
            payload = read_gzip_json(raw_path)
            if not isinstance(payload, list):
                raise ValueError(f"Station payload is not a list: {raw_path}")
            frame = normalizer(payload, timestamp_from_path(raw_path))
            validate_snapshot(frame)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = output_path.with_suffix(".parquet.tmp")
            frame.write_parquet(temporary_path, compression="zstd", statistics=True)
            temporary_path.replace(output_path)
            totals["written_files"] += 1
            totals["rows"] += frame.height
    return totals


def build_weather_parquet(raw_root: Path, processed_root: Path) -> dict[str, int]:
    totals = {"raw_files": 0, "written_files": 0, "skipped_files": 0, "rows": 0}
    source_root = raw_root / "source=weather_forecast"
    for raw_path in sorted(source_root.glob("date=*/hour=*/*.json.gz")):
        totals["raw_files"] += 1
        relative = raw_path.relative_to(raw_root)
        output_path = (
            (processed_root / "weather_forecasts" / relative)
            .with_suffix("")
            .with_suffix(".parquet")
        )
        if output_path.exists():
            totals["skipped_files"] += 1
            continue
        payload = read_gzip_json(raw_path)
        if not isinstance(payload, dict) or not isinstance(payload.get("locations"), list):
            raise ValueError(f"Invalid weather forecast envelope: {raw_path}")
        issued_at = datetime.fromisoformat(str(payload["issued_at"]))
        rows: list[dict[str, object]] = []
        for grid_id, location in enumerate(payload["locations"]):
            hourly = location.get("hourly", {})
            times = hourly.get("time", [])
            for index, local_time in enumerate(times):
                rows.append(
                    {
                        "grid_id": grid_id,
                        "grid_latitude": float(location["latitude"]),
                        "grid_longitude": float(location["longitude"]),
                        "issued_at": issued_at,
                        "forecast_time": datetime.fromisoformat(local_time)
                        .replace(tzinfo=ZoneInfo("Asia/Taipei"))
                        .astimezone(UTC),
                        "temperature_2m": _hourly_value(hourly, "temperature_2m", index),
                        "apparent_temperature": _hourly_value(
                            hourly, "apparent_temperature", index
                        ),
                        "relative_humidity_2m": _hourly_value(
                            hourly, "relative_humidity_2m", index
                        ),
                        "precipitation": _hourly_value(hourly, "precipitation", index),
                        "precipitation_probability": _hourly_value(
                            hourly, "precipitation_probability", index
                        ),
                        "weather_code": _hourly_value(hourly, "weather_code", index),
                        "wind_speed_10m": _hourly_value(hourly, "wind_speed_10m", index),
                        "wind_gusts_10m": _hourly_value(hourly, "wind_gusts_10m", index),
                    }
                )
        import polars as pl

        frame = pl.DataFrame(rows)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = output_path.with_suffix(".parquet.tmp")
        frame.write_parquet(temporary_path, compression="zstd", statistics=True)
        temporary_path.replace(output_path)
        totals["written_files"] += 1
        totals["rows"] += frame.height
    return totals


def _hourly_value(hourly: dict, field: str, index: int) -> object:
    values = hourly.get(field, [])
    return values[index] if index < len(values) else None


def write_manifest(
    processed_root: Path, station_totals: dict[str, int], weather_totals: dict[str, int]
) -> Path:
    manifest_dir = processed_root / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    output_path = manifest_dir / f"dataset-{now:%Y%m%dT%H%M%SZ}.json"
    output_path.write_text(
        json.dumps(
            {
                "created_at": now.isoformat(),
                "pipeline_version": "0.1.0",
                "station_snapshots": station_totals,
                "weather_forecasts": weather_totals,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build reproducible Parquet data from raw snapshots"
    )
    parser.add_argument("--raw-dir", type=Path, default=settings.cloud_raw_dir)
    parser.add_argument("--processed-dir", type=Path, default=settings.formal_processed_dir)
    args = parser.parse_args()
    station_totals = build_station_parquet(args.raw_dir, args.processed_dir)
    weather_totals = build_weather_parquet(args.raw_dir, args.processed_dir)
    manifest = write_manifest(args.processed_dir, station_totals, weather_totals)
    print(
        json.dumps(
            {
                "manifest": str(manifest),
                "station_snapshots": station_totals,
                "weather_forecasts": weather_totals,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

