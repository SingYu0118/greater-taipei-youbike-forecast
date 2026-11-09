from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from youbike_forecast.config import Settings


@dataclass(frozen=True)
class StoredObject:
    key: str
    checksum_sha256: str
    byte_count: int


class RawStorage(Protocol):
    def put_json(self, source: str, fetched_at: datetime, payload: Any) -> StoredObject: ...


def object_key(source: str, fetched_at: datetime, checksum: str) -> str:
    return (
        f"source={source}/date={fetched_at:%Y-%m-%d}/hour={fetched_at:%H}/"
        f"{fetched_at:%Y%m%dT%H%M%S.%fZ}-{checksum[:12]}.json.gz"
    )


class LocalRawStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put_json(self, source: str, fetched_at: datetime, payload: Any) -> StoredObject:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        checksum = hashlib.sha256(body).hexdigest()
        compressed = gzip.compress(body, compresslevel=6, mtime=0)
        key = object_key(source, fetched_at, checksum)
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", dir=destination.parent
            )
            try:
                with os.fdopen(file_descriptor, "wb") as temporary_file:
                    temporary_file.write(compressed)
                    temporary_file.flush()
                    os.fsync(temporary_file.fileno())
                os.replace(temporary_name, destination)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
        return StoredObject(key=key, checksum_sha256=checksum, byte_count=len(compressed))


class R2RawStorage:
    def __init__(self, settings: Settings) -> None:
        import boto3

        required = {
            "R2_ENDPOINT_URL": settings.r2_endpoint_url,
            "R2_ACCESS_KEY_ID": settings.r2_access_key_id,
            "R2_SECRET_ACCESS_KEY": settings.r2_secret_access_key,
            "R2_BUCKET": settings.r2_bucket,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing R2 configuration: {', '.join(missing)}")
        self.bucket = settings.r2_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )

    def put_json(self, source: str, fetched_at: datetime, payload: Any) -> StoredObject:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        checksum = hashlib.sha256(body).hexdigest()
        compressed = gzip.compress(body, compresslevel=6, mtime=0)
        key = object_key(source, fetched_at, checksum)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=compressed,
            ContentType="application/json",
            ContentEncoding="gzip",
            Metadata={"sha256": checksum, "fetched-at": fetched_at.isoformat()},
        )
        return StoredObject(key=key, checksum_sha256=checksum, byte_count=len(compressed))


def storage_from_settings(settings: Settings) -> RawStorage:
    if settings.r2_bucket:
        return R2RawStorage(settings)
    return LocalRawStorage(settings.raw_dir)

