from __future__ import annotations

import argparse
import asyncio
import json
import signal
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from youbike_forecast.collectors.client import CollectionResult, Collector, PartialCollectionError
from youbike_forecast.collectors.storage import storage_from_settings
from youbike_forecast.config import settings


async def run_scheduler(interval_minutes: int, log_path: Path) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, stop.set)
    collector = Collector(settings, storage_from_settings(settings))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    while not stop.is_set():
        started_at = datetime.now(UTC)
        entry: dict[str, object] = {"started_at": started_at.isoformat()}
        try:
            include_weather = started_at.minute < interval_minutes
            results = await collector.collect_all(include_weather=include_weather)
            entry["status"] = "success"
            entry["results"] = _serialize_results(results)
        except PartialCollectionError as error:
            entry["status"] = "partial_failure"
            entry["results"] = _serialize_results(error.successful)
            entry["errors"] = error.failures
        except Exception as error:  # The scheduler must survive a failed run.
            entry["status"] = "failure"
            entry["error"] = f"{type(error).__name__}: {error}"
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        now = datetime.now(UTC)
        next_minute = ((now.minute // interval_minutes) + 1) * interval_minutes
        next_run = now.replace(second=0, microsecond=0)
        if next_minute >= 60:
            next_run = next_run.replace(minute=0) + timedelta(hours=1)
        else:
            next_run = next_run.replace(minute=next_minute)
        try:
            await asyncio.wait_for(stop.wait(), timeout=max((next_run - now).total_seconds(), 1))
        except TimeoutError:
            pass


def _serialize_results(results: list[CollectionResult]) -> list[dict[str, object]]:
    return [
        {
            **asdict(result),
            "fetched_at": result.fetched_at.isoformat(),
            "stored": asdict(result.stored),
        }
        for result in results
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the resilient local collection scheduler")
    parser.add_argument("--interval-minutes", type=int, default=5)
    parser.add_argument("--log", type=Path, default=settings.data_dir / "logs" / "collector.jsonl")
    args = parser.parse_args()
    if 60 % args.interval_minutes:
        raise ValueError("interval-minutes must divide evenly into 60")
    asyncio.run(run_scheduler(args.interval_minutes, args.log))


if __name__ == "__main__":
    main()
