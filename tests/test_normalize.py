from datetime import UTC, datetime

from youbike_forecast.pipeline.normalize import (
    normalize_new_taipei,
    normalize_taipei,
    validate_snapshot,
)


def test_normalize_taipei_snapshot() -> None:
    fetched_at = datetime(2026, 11, 9, 7, tzinfo=UTC)
    frame = normalize_taipei(
        [
            {
                "sno": "500101001",
                "sna": "YouBike2.0_Test",
                "sarea": "Daan",
                "ar": "Address",
                "latitude": 25.0,
                "longitude": 121.5,
                "Quantity": 20,
                "available_rent_bikes": 7,
                "available_return_bikes": 13,
                "act": "1",
                "infoTime": "2026-11-09 15:00:00",
            }
        ],
        fetched_at,
    )
    validate_snapshot(frame)
    assert frame.row(0, named=True)["station_name"] == "Test"
    assert frame.row(0, named=True)["available_bikes"] == 7


def test_normalize_new_taipei_preserves_bike_types() -> None:
    fetched_at = datetime(2026, 11, 9, 7, tzinfo=UTC)
    frame = normalize_new_taipei(
        [
            {
                "sno": "500201001",
                "sna": "YouBike2.0_Test",
                "sarea": "Bali",
                "ar": "Address",
                "lat": "25.1",
                "lng": "121.4",
                "tot_quantity": "20",
                "sbi_quantity": "7",
                "bemp": "13",
                "yb2_quantity": "5",
                "eyb_quantity": "2",
                "act": "1",
                "mday": "20261109T150000",
            }
        ],
        fetched_at,
    )
    validate_snapshot(frame)
    row = frame.row(0, named=True)
    assert row["mechanical_bikes"] == 5
    assert row["electric_bikes"] == 2

