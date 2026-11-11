import gzip
import json
from datetime import UTC, datetime

from youbike_forecast.collectors.storage import LocalRawStorage, storage_from_settings
from youbike_forecast.config import Settings


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


def test_r2_read_credentials_do_not_switch_local_collector_backend(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        raw_storage_backend="local",
        r2_endpoint_url="https://example.r2.cloudflarestorage.com",
        r2_access_key_id="read-only-key",
        r2_secret_access_key="read-only-secret",
        r2_bucket="bucket",
    )
    assert isinstance(storage_from_settings(settings), LocalRawStorage)

