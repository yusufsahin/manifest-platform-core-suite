from __future__ import annotations

from typing import Any

import pytest

from tooling.mpc_runtime.storage.blob_store import S3BlobStore


def test_s3_blob_store_put_get_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    storage: dict[str, bytes] = {}

    class FakeBody:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def read(self) -> bytes:
            return self._data

    class FakeS3Client:
        def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
            storage[f"{Bucket}/{Key}"] = Body

        def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
            key = f"{Bucket}/{Key}"
            if key not in storage:
                raise KeyError(key)
            return {"Body": FakeBody(storage[key])}

    def fake_client(service_name: str, region_name: str | None = None) -> FakeS3Client:
        assert service_name == "s3"
        return FakeS3Client()

    monkeypatch.setattr("boto3.client", fake_client)

    store = S3BlobStore(bucket="my-bucket", prefix="pfx", region="us-east-1")
    ref = store.put_text(key="abc123", text="hello s3")
    assert ref.startswith("s3://my-bucket/")
    assert store.get_text(ref=ref) == "hello s3"


def test_s3_blob_store_get_rejects_non_s3_ref() -> None:
    store = S3BlobStore(bucket="b", prefix="p")
    with pytest.raises(ValueError, match="Invalid S3 ref"):
        store.get_text(ref="file:///tmp/x")
