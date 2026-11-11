import gzip
import hashlib

import pytest

from youbike_forecast.config import Settings
from youbike_forecast.pipeline.r2_sync import (
    atomic_write,
    destination_for_key,
    verify_source_object,
)


def test_r2_source_destination_and_checksum(tmp_path) -> None:
    config = Settings(_env_file=None, data_dir=tmp_path)
    body = b'[{"station_id":"one","bikes":3}]'
    checksum = hashlib.sha256(body).hexdigest()
    key = f"source=taipei/date=2026-11-11/hour=02/snapshot-{checksum[:12]}.json.gz"
    compressed = gzip.compress(body, mtime=0)

    verify_source_object(key, compressed, {"sha256": checksum})
    destination = destination_for_key(config, key)
    atomic_write(destination, compressed)

    assert destination == tmp_path / "raw" / key
    assert destination.read_bytes() == compressed


def test_r2_sync_rejects_checksum_mismatch() -> None:
    body = b"[]"
    compressed = gzip.compress(body, mtime=0)
    with pytest.raises(ValueError, match="metadata checksum mismatch"):
        verify_source_object(
            "source=taipei/date=2026-11-11/hour=02/snapshot-deadbeef0000.json.gz",
            compressed,
            {"sha256": "not-the-checksum"},
        )


def test_cloud_evidence_destination_is_separate(tmp_path) -> None:
    config = Settings(_env_file=None, data_dir=tmp_path)
    assert destination_for_key(config, "control/collection-quality.json") == (
        tmp_path / "cloud_evidence" / "control" / "collection-quality.json"
    )
