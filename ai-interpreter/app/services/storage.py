"""Blob storage for VIA images.

Two back-ends behind one tiny interface:

* ``S3Storage``    - any S3-compatible object store (MinIO in production).
                     Selected when ``S3_ENDPOINT`` (or ``S3_BUCKET_NAME`` with
                     AWS credentials) is configured.
* ``LocalStorage`` - files under ``UPLOAD_DIR``. Used for tests and local dev
                     when no S3 settings are present.

Keys are relative paths such as ``<sha256>.jpg``; ``S3_PREFIX`` lets several
services share one bucket (``interpreter/``, ``backend/`` ...).
"""
from __future__ import annotations

import logging
from pathlib import Path

from flask import current_app

log = logging.getLogger(__name__)


class StorageError(RuntimeError):
    pass


class LocalStorage:
    backend = "local"

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise StorageError(f"Invalid storage key: {key}")
        return path

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()


class S3Storage:
    backend = "s3"

    def __init__(self, *, endpoint: str, access_key: str, secret_key: str, bucket: str,
                 region: str = "us-east-1", path_style: bool = True, prefix: str = ""):
        import boto3
        from botocore.config import Config as BotoConfig

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
            region_name=region or "us-east-1",
            config=BotoConfig(
                s3={"addressing_style": "path" if path_style else "auto"},
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 3},
            ),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError

        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in ("404", "NoSuchBucket"):
                raise StorageError(f"Cannot access bucket {self.bucket!r}: {exc}") from exc
            log.info("Creating missing bucket %s", self.bucket)
            self.client.create_bucket(Bucket=self.bucket)

    def _key(self, key: str) -> str:
        key = key.lstrip("/")
        return f"{self.prefix}/{key}" if self.prefix else key

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise StorageError(str(exc)) from exc

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        from botocore.exceptions import ClientError

        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                raise FileNotFoundError(key) from exc
            raise StorageError(str(exc)) from exc
        return obj["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))


def build_storage(config) -> LocalStorage | S3Storage:
    """Pick the storage back-end from the Flask config (see Config in config.py)."""
    if config.get("S3_ENDPOINT") or (config.get("S3_BUCKET_NAME") and config.get("S3_ACCESS_KEY")):
        return S3Storage(
            endpoint=config.get("S3_ENDPOINT", ""),
            access_key=config.get("S3_ACCESS_KEY", ""),
            secret_key=config.get("S3_SECRET_KEY", ""),
            bucket=config.get("S3_BUCKET_NAME") or "via-images",
            region=config.get("S3_REGION", "us-east-1"),
            path_style=bool(config.get("S3_FORCE_PATH_STYLE", True)),
            prefix=config.get("S3_PREFIX", ""),
        )
    return LocalStorage(Path(config["UPLOAD_DIR"]))


def get_storage():
    """Storage instance for the current app (created once per app, cached on the app)."""
    app = current_app._get_current_object()
    storage = app.extensions.get("viscan_storage")
    if storage is None:
        storage = build_storage(app.config)
        app.extensions["viscan_storage"] = storage
        app.logger.info("Image storage backend: %s", storage.backend)
    return storage
