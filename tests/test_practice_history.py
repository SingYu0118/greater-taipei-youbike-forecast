from datetime import date
from pathlib import Path

import polars as pl

from youbike_forecast.pipeline.practice_history import build_practice_parquet


def test_practice_history_is_normalized_and_physically_separate(tmp_path: Path) -> None:
    download = tmp_path / "downloads"
    (download / "sites").mkdir(parents=True)
    (download / "slots").mkdir(parents=True)
    (download / "sites" / "2025-06-22.csv").write_text(
        "sno,sna,sarea,latitude,longitude,ar,sareaen,aren,act\n"
        "500101001,YouBike2.0_Test A,Daan,25.0,121.5,Address,Daan,Address,1\n"
        "500101002,YouBike2.0_Test B,Xinyi,25.1,121.6,Address,Xinyi,Address,1\n",
        encoding="utf-8",
    )
    (download / "slots" / "2025-06-22.csv").write_text(
        "sno,total,available_rent_bikes,available_return_bikes,infoTime\n"
        "500101001,20,7,13,2025-06-22 00:00:00\n"
        "500101002,30,11,19,2025-06-22 00:00:00\n"
        "500101002,30,31,0,2025-06-22 00:10:00\n",
        encoding="utf-8",
    )

    processed = tmp_path / "practice_processed"
    report = build_practice_parquet(
        download,
        processed,
        date(2025, 6, 22),
        date(2025, 6, 22),
        station_limit=None,
    )

    station_file = next((processed / "station_snapshots").glob("**/*.parquet"))
    frame = pl.read_parquet(station_file)
    assert report["formal_evidence_eligible"] is False
    assert report["written_rows"] == 2
    assert report["dropped_rows"] == 1
    assert frame.get_column("source").unique().to_list() == ["taipei"]
    assert frame.get_column("station_name").to_list() == ["Test A", "Test B"]
    assert str(frame.schema["fetched_at"]) == "Datetime(time_unit='us', time_zone='UTC')"
    weather_path = processed / "weather_forecasts" / "practice-null-weather.parquet"
    assert weather_path.exists()
    assert pl.read_parquet(weather_path).get_column("temperature_2m").unique().to_list() == [
        0.0
    ]
