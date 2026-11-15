from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

from youbike_forecast.collectors.client import NEW_TAIPEI_URL, TAIPEI_URL
from youbike_forecast.config import Settings, settings
from youbike_forecast.models.service import ForecastService
from youbike_forecast.pipeline.r2_sync import atomic_write, r2_client

DEFAULT_KEY = "control/latest-forecasts.json"


def fetch_official_translations(
    config: Settings = settings,
) -> dict[tuple[str, str], dict[str, str]]:
    translations: dict[tuple[str, str], dict[str, str]] = {}
    timeout = httpx.Timeout(config.request_timeout_seconds)
    headers = {"User-Agent": "greater-taipei-youbike-forecast/0.1"}
    with httpx.Client(timeout=timeout, headers=headers) as client:
        taipei_response = client.get(TAIPEI_URL)
        taipei_response.raise_for_status()
        taipei_rows = taipei_response.json()
        if not isinstance(taipei_rows, list) or not taipei_rows:
            raise ValueError("Taipei translation payload must be a non-empty list")
        _add_translations(translations, "taipei", taipei_rows)

        page = 0
        while True:
            new_taipei_response = client.get(
                NEW_TAIPEI_URL,
                params={"page": page, "size": config.ntpc_page_size},
            )
            new_taipei_response.raise_for_status()
            batch = new_taipei_response.json()
            if not isinstance(batch, list):
                raise ValueError(f"New Taipei translation page {page} is not a list")
            _add_translations(translations, "new_taipei", batch)
            if len(batch) < config.ntpc_page_size:
                break
            page += 1
            if page > 20:
                raise ValueError("New Taipei translation pagination exceeded safety limit")
    return translations


def _add_translations(
    destination: dict[tuple[str, str], dict[str, str]],
    source: str,
    rows: list[dict[str, Any]],
) -> None:
    for row in rows:
        station_id = str(row.get("sno", ""))
        if not station_id:
            continue
        destination[(source, station_id)] = {
            "station_name_en": str(row.get("snaen") or "").removeprefix("YouBike2.0_"),
            "district_en": str(row.get("sareaen") or ""),
        }


def enrich_official_translations(
    snapshot: dict[str, Any],
    translations: dict[tuple[str, str], dict[str, str]],
) -> None:
    for station in snapshot["stations"]:
        official = translations.get((str(station["source"]), str(station["station_id"])), {})
        station.update(official)


def publish_forecast_snapshot(
    config: Settings = settings,
    *,
    key: str = DEFAULT_KEY,
    local_output: Path | None = Path("artifacts/serving/latest-forecasts.json"),
    upload: bool = True,
) -> dict[str, Any]:
    service = ForecastService(config.model_dir, config.formal_feature_path)
    if not service.is_ready():
        raise RuntimeError("Validated model artifacts and inference features are not ready")
    snapshot = service.forecast_snapshot()
    enrich_official_translations(snapshot, fetch_official_translations(config))
    body = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    checksum = hashlib.sha256(body).hexdigest()

    if local_output is not None:
        atomic_write(local_output, body)

    if upload:
        client, bucket = r2_client(config)
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            CacheControl="public, max-age=60",
            Metadata={
                "sha256": checksum,
                "model-id": str(snapshot["model"]["model_id"]),
                "forecast-as-of": str(snapshot["as_of"]),
            },
        )
    return {
        "key": key,
        "model_id": snapshot["model"]["model_id"],
        "as_of": snapshot["as_of"],
        "stations": snapshot["count"],
        "bytes": len(body),
        "sha256": checksum,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish a validated station forecast snapshot to Cloudflare R2"
    )
    parser.add_argument("--key", default=DEFAULT_KEY)
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument(
        "--local-output",
        type=Path,
        default=Path("artifacts/serving/latest-forecasts.json"),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            publish_forecast_snapshot(
                settings,
                key=args.key,
                local_output=args.local_output,
                upload=not args.local_only,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
