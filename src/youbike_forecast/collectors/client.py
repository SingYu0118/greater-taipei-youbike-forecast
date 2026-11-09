from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from youbike_forecast.collectors.storage import RawStorage, StoredObject
from youbike_forecast.config import Settings

TAIPEI_URL = "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json"
NEW_TAIPEI_URL = (
    "https://data.ntpc.gov.tw/api/datasets/010e5b15-3823-4b20-b401-b1cf000550c5/json"
)
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class CollectionResult:
    source: str
    fetched_at: datetime
    records: int
    duration_ms: int
    stored: StoredObject


class Collector:
    def __init__(self, settings: Settings, storage: RawStorage) -> None:
        self.settings = settings
        self.storage = storage

    async def _get_json(
        self, client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None
    ) -> Any:
        error: Exception | None = None
        for attempt in range(self.settings.request_attempts):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                error = exc
                if attempt + 1 == self.settings.request_attempts:
                    break
                await asyncio.sleep((2**attempt) + random.random())
        raise RuntimeError(f"Request failed after retries: {url}") from error

    async def collect_taipei(self, client: httpx.AsyncClient) -> CollectionResult:
        started = time.monotonic()
        payload = await self._get_json(client, TAIPEI_URL)
        if not isinstance(payload, list) or not payload:
            raise ValueError("Taipei payload must be a non-empty list")
        fetched_at = datetime.now(UTC)
        stored = self.storage.put_json("taipei", fetched_at, payload)
        return CollectionResult(
            "taipei", fetched_at, len(payload), round((time.monotonic() - started) * 1000), stored
        )

    async def collect_new_taipei(self, client: httpx.AsyncClient) -> CollectionResult:
        started = time.monotonic()
        records: list[dict[str, Any]] = []
        page = 0
        while True:
            batch = await self._get_json(
                client,
                NEW_TAIPEI_URL,
                {"page": page, "size": self.settings.ntpc_page_size},
            )
            if not isinstance(batch, list):
                raise ValueError(f"New Taipei page {page} is not a list")
            records.extend(batch)
            if len(batch) < self.settings.ntpc_page_size:
                break
            page += 1
            if page > 20:
                raise ValueError("New Taipei pagination exceeded safety limit")
        if not records:
            raise ValueError("New Taipei payload is empty")
        station_ids = [record.get("sno") for record in records]
        if len(station_ids) != len(set(station_ids)):
            raise ValueError("New Taipei payload contains duplicate station IDs across pages")
        fetched_at = datetime.now(UTC)
        stored = self.storage.put_json("new_taipei", fetched_at, records)
        return CollectionResult(
            "new_taipei",
            fetched_at,
            len(records),
            round((time.monotonic() - started) * 1000),
            stored,
        )

    async def collect_weather(self, client: httpx.AsyncClient) -> CollectionResult:
        started = time.monotonic()
        payload = await self._get_json(
            client,
            OPEN_METEO_URL,
            {
                "latitude": "25.0375,25.1000,24.9900",
                "longitude": "121.5637,121.5000,121.7000",
                "hourly": (
                    "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,"
                    "precipitation_probability,weather_code,wind_speed_10m,wind_gusts_10m"
                ),
                "forecast_hours": 48,
                "timezone": "Asia/Taipei",
            },
        )
        if not isinstance(payload, list) or len(payload) != 3:
            raise ValueError("Weather payload must contain all three Greater Taipei grid points")
        fetched_at = datetime.now(UTC)
        envelope = {"issued_at": fetched_at.isoformat(), "locations": payload}
        stored = self.storage.put_json("weather_forecast", fetched_at, envelope)
        return CollectionResult(
            "weather_forecast",
            fetched_at,
            len(payload),
            round((time.monotonic() - started) * 1000),
            stored,
        )

    async def collect_all(self, include_weather: bool = True) -> list[CollectionResult]:
        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        headers = {"User-Agent": "greater-taipei-youbike-forecast/0.1"}
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            tasks = [self.collect_taipei(client), self.collect_new_taipei(client)]
            if include_weather:
                tasks.append(self.collect_weather(client))
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        failures = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
        results = [outcome for outcome in outcomes if isinstance(outcome, CollectionResult)]
        if failures:
            messages = "; ".join(str(failure) for failure in failures)
            raise RuntimeError(f"Partial collection failure ({len(results)} succeeded): {messages}")
        return results

