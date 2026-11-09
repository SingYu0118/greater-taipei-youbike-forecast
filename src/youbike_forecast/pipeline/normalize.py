from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import polars as pl

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


def _integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def normalize_taipei(records: list[dict[str, Any]], fetched_at: datetime) -> pl.DataFrame:
    rows = []
    for record in records:
        rows.append(
            {
                "source": "taipei",
                "station_id": str(record["sno"]),
                "station_name": str(record["sna"]).removeprefix("YouBike2.0_"),
                "district": record.get("sarea"),
                "address": record.get("ar"),
                "latitude": _float(record.get("latitude")),
                "longitude": _float(record.get("longitude")),
                "capacity": _integer(record.get("Quantity")),
                "available_bikes": _integer(record.get("available_rent_bikes")),
                "available_docks": _integer(record.get("available_return_bikes")),
                "mechanical_bikes": _integer(record.get("available_rent_bikes")),
                "electric_bikes": None,
                "is_active": str(record.get("act")) == "1",
                "source_updated_at": _parse_datetime(record.get("infoTime")),
                "fetched_at": fetched_at,
            }
        )
    return pl.DataFrame(rows).select(NORMALIZED_COLUMNS)


def normalize_new_taipei(records: list[dict[str, Any]], fetched_at: datetime) -> pl.DataFrame:
    rows = []
    for record in records:
        rows.append(
            {
                "source": "new_taipei",
                "station_id": str(record["sno"]),
                "station_name": str(record["sna"]).removeprefix("YouBike2.0_"),
                "district": record.get("sarea"),
                "address": record.get("ar"),
                "latitude": _float(record.get("lat")),
                "longitude": _float(record.get("lng")),
                "capacity": _integer(record.get("tot_quantity")),
                "available_bikes": _integer(record.get("sbi_quantity")),
                "available_docks": _integer(record.get("bemp")),
                "mechanical_bikes": _integer(record.get("yb2_quantity")),
                "electric_bikes": _integer(record.get("eyb_quantity")),
                "is_active": str(record.get("act")) == "1",
                "source_updated_at": _parse_datetime(record.get("mday")),
                "fetched_at": fetched_at,
            }
        )
    return pl.DataFrame(rows).select(NORMALIZED_COLUMNS)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y%m%dT%H%M%S"):
        try:
            local = datetime.strptime(text, pattern)
            timezone = __import__("zoneinfo").ZoneInfo("Asia/Taipei")
            return local.replace(tzinfo=timezone).astimezone(UTC)
        except ValueError:
            continue
    raise ValueError(f"Unsupported source timestamp: {value}")


def validate_snapshot(frame: pl.DataFrame) -> None:
    if frame.is_empty():
        raise ValueError("Normalized snapshot is empty")
    duplicate_count = frame.select(pl.col("station_id").is_duplicated().sum()).item()
    if duplicate_count:
        raise ValueError(f"Snapshot contains {duplicate_count} duplicate station IDs")
    invalid = frame.filter(
        (pl.col("capacity") < 0)
        | (pl.col("available_bikes") < 0)
        | (pl.col("available_docks") < 0)
        | (pl.col("available_bikes") > pl.col("capacity"))
    )
    if invalid.height:
        raise ValueError(f"Snapshot contains {invalid.height} impossible inventory rows")

