import gzip
import json
from datetime import UTC, datetime

from youbike_forecast.collectors.storage import LocalRawStorage


def test_local_storage_is_deterministic_and_readable(tmp_path) -> None:
    storage = LocalRawStorage(tmp_path)
    fetched_at = datetime(2026, 11, 9, 12, 30, tzinfo=UTC)
    payload = [{"station_id": "one", "bikes": 3}]
    first = storage.put_json("test", fetched_at, payload)
    second = storage.put_json("test", fetched_at, payload)
    assert first == second
    path = tmp_path / first.key
    assert path.exists()
    with gzip.open(path, "rt", encoding="utf-8") as stored:
        assert json.load(stored) == payload

