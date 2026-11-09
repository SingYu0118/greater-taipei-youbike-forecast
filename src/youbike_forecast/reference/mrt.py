from __future__ import annotations

import argparse
import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

DATASET_PAGE = "https://data.taipei/dataset/detail?id=1eefa68d-7c8d-491b-8e75-66a161947426"
RESOURCE_URL = (
    "https://data.taipei/api/frontstage/tpeod/dataset/resource.download"
    "?rid=c77e91bf-067c-475e-917b-545ff62b7d76"
)


def _array_value(value: str) -> list[str]:
    cleaned = value.strip().strip("'").strip("{}").strip()
    return [part.strip() for part in cleaned.split(",")]


def fetch_mrt_stations(output: Path) -> dict[str, object]:
    response = httpx.get(
        RESOURCE_URL,
        headers={"User-Agent": "greater-taipei-youbike-forecast/0.1"},
        timeout=60,
        follow_redirects=True,
    )
    response.raise_for_status()
    reader = csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")))
    rows: list[dict[str, object]] = []
    latest_source_update = ""
    for source_row in reader:
        names = _array_value(source_row["StationName"])
        position = _array_value(source_row["StationPosition"])
        if len(position) != 2:
            raise ValueError(f"Invalid StationPosition: {source_row['StationPosition']}")
        rows.append(
            {
                "mrt_station_name": names[0],
                "mrt_station_name_en": names[1] if len(names) > 1 else "",
                "latitude": float(position[1]),
                "longitude": float(position[0]),
                "station_id": source_row["StationID"].strip("'"),
                "source_updated_at": source_row["UpdateTime"],
            }
        )
        latest_source_update = max(latest_source_update, source_row["UpdateTime"])
    if len(rows) < 100:
        raise ValueError(f"Official MRT dataset returned only {len(rows)} rows")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "created_at": datetime.now(UTC).isoformat(),
        "source": "Taipei City Data Platform - Taipei Metro Station Data Service",
        "dataset_page": DATASET_PAGE,
        "resource_url": RESOURCE_URL,
        "license": "Taiwan Government Open Data License 1.0",
        "latest_source_update": latest_source_update,
        "rows": len(rows),
        "output": str(output),
    }
    output.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch official Greater Taipei MRT station coordinates"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/reference/greater_taipei_mrt_stations.csv")
    )
    args = parser.parse_args()
    print(json.dumps(fetch_mrt_stations(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
