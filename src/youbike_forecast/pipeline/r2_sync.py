from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from youbike_forecast.config import Settings, settings

DEFAULT_PREFIXES = ("source=", "manifests/", "control/")


def r2_client(config: Settings) -> tuple[Any, str]:
    import boto3

    required = {
        "R2_ENDPOINT_URL": config.r2_endpoint_url,
        "R2_ACCESS_KEY_ID": config.r2_access_key_id,
        "R2_SECRET_ACCESS_KEY": config.r2_secret_access_key,
        "R2_BUCKET": config.r2_bucket,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"Missing R2 configuration: {', '.join(missing)}")
    client = boto3.client(
        "s3",
        endpoint_url=config.r2_endpoint_url,
        aws_access_key_id=config.r2_access_key_id,
        aws_secret_access_key=config.r2_secret_access_key,
        region_name="auto",
    )
    return client, str(config.r2_bucket)


def destination_for_key(config: Settings, key: str) -> Path:
    if key.startswith("source="):
        return config.cloud_raw_dir / key
    return config.data_dir / "cloud_evidence" / key


def verify_source_object(key: str, compressed: bytes, metadata: dict[str, str]) -> None:
    try:
        body = gzip.decompress(compressed)
    except (gzip.BadGzipFile, EOFError) as error:
        raise ValueError(f"R2 object is not valid gzip: {key}") from error
    checksum = hashlib.sha256(body).hexdigest()
    metadata_checksum = metadata.get("sha256")
    if metadata_checksum and checksum != metadata_checksum:
        raise ValueError(f"R2 metadata checksum mismatch: {key}")
    filename_checksum = Path(key).name.rsplit("-", 1)[-1].removesuffix(".json.gz")
    if filename_checksum and not checksum.startswith(filename_checksum):
        raise ValueError(f"R2 filename checksum mismatch: {key}")


def atomic_write(destination: Path, payload: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(payload)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, destination)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def sync_r2(config: Settings, prefixes: tuple[str, ...] = DEFAULT_PREFIXES) -> dict[str, int]:
    client, bucket = r2_client(config)
    summary = {"listed": 0, "downloaded": 0, "skipped": 0, "verified": 0, "bytes": 0}
    paginator = client.get_paginator("list_objects_v2")
    for prefix in prefixes:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = str(item["Key"])
                size = int(item.get("Size", 0))
                summary["listed"] += 1
                destination = destination_for_key(config, key)
                immutable = key.startswith("source=") or key.startswith("manifests/")
                if immutable and destination.exists() and destination.stat().st_size == size:
                    summary["skipped"] += 1
                    continue
                response = client.get_object(Bucket=bucket, Key=key)
                payload = response["Body"].read()
                if len(payload) != size:
                    raise ValueError(f"R2 size mismatch: {key}")
                if key.startswith("source="):
                    verify_source_object(key, payload, response.get("Metadata", {}))
                    summary["verified"] += 1
                atomic_write(destination, payload)
                summary["downloaded"] += 1
                summary["bytes"] += len(payload)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync immutable Cloudflare R2 evidence into the local reproducible pipeline"
    )
    parser.add_argument("--prefix", action="append", dest="prefixes")
    args = parser.parse_args()
    prefixes = tuple(args.prefixes) if args.prefixes else DEFAULT_PREFIXES
    print(json.dumps(sync_r2(settings, prefixes), indent=2))


if __name__ == "__main__":
    main()
