from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LocalFsBlobStore:
    """Local filesystem 'blob store' for dev/tests.

    This is a stand-in for a real object store (S3/GCS/Azure Blob).
    """

    root_dir: str

    def put_text(self, *, key: str, text: str) -> str:
        os.makedirs(self.root_dir, exist_ok=True)
        # Key is expected to be deterministic (e.g., checksum/hash).
        path = os.path.join(self.root_dir, f"{key}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def get_text(self, *, ref: str) -> str:
        with open(ref, "r", encoding="utf-8") as f:
            return f.read()


@dataclass
class S3BlobStore:
    """AWS S3-backed blob store.

    Requires boto3 at runtime when MPC_RUNTIME_BLOB_BACKEND=s3.
    Ref format: s3://{bucket}/{key}
    """

    bucket: str
    prefix: str = "mpc-runtime"
    region: str | None = None

    def _client(self):
        try:
            import boto3  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("boto3 is required for S3BlobStore") from exc
        return boto3.client("s3", region_name=self.region)

    def _obj_key(self, key: str) -> str:
        p = self.prefix.strip("/")
        return f"{p}/{key}.txt" if p else f"{key}.txt"

    def put_text(self, *, key: str, text: str) -> str:
        client = self._client()
        obj_key = self._obj_key(key)
        client.put_object(Bucket=self.bucket, Key=obj_key, Body=text.encode("utf-8"), ContentType="text/plain; charset=utf-8")
        return f"s3://{self.bucket}/{obj_key}"

    def get_text(self, *, ref: str) -> str:
        if not ref.startswith("s3://"):
            raise ValueError("Invalid S3 ref")
        # s3://bucket/key...
        _, rest = ref.split("s3://", 1)
        bucket, obj_key = rest.split("/", 1)
        client = self._client()
        resp = client.get_object(Bucket=bucket, Key=obj_key)
        body = resp["Body"].read()
        return body.decode("utf-8")


@dataclass
class StubObjectBlobStore:
    """Placeholder for a real object store client.

    Implementers should provide put/get using signed URLs or SDK clients.
    """

    def put_text(self, *, key: str, text: str) -> str:
        raise NotImplementedError("StubObjectBlobStore requires a real object storage integration.")

    def get_text(self, *, ref: str) -> str:
        raise NotImplementedError("StubObjectBlobStore requires a real object storage integration.")

