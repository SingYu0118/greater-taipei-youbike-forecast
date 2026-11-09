from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict

from youbike_forecast.collectors.client import Collector
from youbike_forecast.collectors.storage import storage_from_settings
from youbike_forecast.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect immutable YouBike and weather snapshots")
    parser.add_argument("--skip-weather", action="store_true")
    args = parser.parse_args()
    collector = Collector(settings, storage_from_settings(settings))
    results = asyncio.run(collector.collect_all(include_weather=not args.skip_weather))
    print(
        json.dumps(
            [
                {
                    **asdict(result),
                    "fetched_at": result.fetched_at.isoformat(),
                    "stored": asdict(result.stored),
                }
                for result in results
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

