from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from .ports import CanaryConfig, RuntimeStore, StoredArtifact


def _k(prefix: str, tenant_id: str, suffix: str) -> str:
    return f"{prefix}:{tenant_id}:{suffix}"


@dataclass
class RedisRuntimeStore(RuntimeStore):
    """Redis-backed store for runtime state.

    Data layout (keys):
    - artifact hash:    art:{tenant}:{id} (hash)
    - artifacts index:  art_index:{tenant} (set of ids)
    - active pointer:   ptr:{tenant}:active (string)
    - prev pointer:     ptr:{tenant}:prev (string)
    - canary:           ptr:{tenant}:canary (hash: artifact_id, weight)
    - mode:             ptr:{tenant}:mode (string)
    - idempotency:      idem:{tenant}:{key} (string JSON, TTL)
    - audit:            audit:{tenant} (list of JSON lines)
    """

    redis: Any

    prefix: str = "mpc_runtime"

    def create_artifact(
        self,
        *,
        tenant_id: str,
        manifest_ref: str,
        checksum: str,
        signature: str | None,
        created_at: str,
    ) -> StoredArtifact:
        artifact_id = uuid.uuid4().hex
        versions = [a.version for a in self.list_artifacts(tenant_id=tenant_id)]
        version = (max(versions) + 1) if versions else 1
        data = {
            "id": artifact_id,
            "tenant_id": tenant_id,
            "status": "draft",
            "version": str(version),
            "checksum": checksum,
            "created_at": created_at,
            "manifest_ref": manifest_ref,
            "signature": signature or "",
        }
        self.redis.hset(_k(self.prefix, tenant_id, f"art:{artifact_id}"), mapping=data)
        self.redis.sadd(_k(self.prefix, tenant_id, "art_index"), artifact_id)
        return self.get_artifact(tenant_id=tenant_id, artifact_id=artifact_id)

    def update_artifact(
        self,
        *,
        tenant_id: str,
        artifact_id: str,
        manifest_ref: str,
        checksum: str,
        signature: str | None,
    ) -> StoredArtifact:
        existing = self.get_artifact(tenant_id=tenant_id, artifact_id=artifact_id)
        mapping = {
            "manifest_ref": manifest_ref,
            "checksum": checksum,
            "signature": signature or "",
            "status": existing.status,
            "version": str(existing.version),
            "created_at": existing.created_at,
            "tenant_id": tenant_id,
            "id": artifact_id,
        }
        self.redis.hset(_k(self.prefix, tenant_id, f"art:{artifact_id}"), mapping=mapping)
        self.redis.sadd(_k(self.prefix, tenant_id, "art_index"), artifact_id)
        return self.get_artifact(tenant_id=tenant_id, artifact_id=artifact_id)

    def get_artifact(self, *, tenant_id: str, artifact_id: str) -> StoredArtifact:
        key = _k(self.prefix, tenant_id, f"art:{artifact_id}")
        data = self.redis.hgetall(key) or {}
        if not data:
            raise KeyError("artifact not found")
        # redis may return bytes
        def _s(v: Any) -> str:
            if isinstance(v, bytes):
                return v.decode("utf-8")
            return str(v)

        signature = _s(data.get(b"signature") if b"signature" in data else data.get("signature"))
        signature = signature or None
        status = _s(data.get(b"status") if b"status" in data else data.get("status"))
        return StoredArtifact(
            id=_s(data.get(b"id") if b"id" in data else data.get("id")),
            tenant_id=_s(data.get(b"tenant_id") if b"tenant_id" in data else data.get("tenant_id")),
            status=str(status),
            version=int(_s(data.get(b"version") if b"version" in data else data.get("version"))),
            checksum=_s(data.get(b"checksum") if b"checksum" in data else data.get("checksum")),
            created_at=_s(data.get(b"created_at") if b"created_at" in data else data.get("created_at")),
            manifest_ref=_s(data.get(b"manifest_ref") if b"manifest_ref" in data else data.get("manifest_ref")),
            signature=signature,
        )

    def _set_status(self, *, tenant_id: str, artifact_id: str, status: str) -> None:
        key = _k(self.prefix, tenant_id, f"art:{artifact_id}")
        if not self.redis.exists(key):
            raise KeyError("artifact not found")
        self.redis.hset(key, mapping={"status": status})

    def list_artifacts(self, *, tenant_id: str) -> list[StoredArtifact]:
        ids = self.redis.smembers(_k(self.prefix, tenant_id, "art_index")) or set()
        out: list[StoredArtifact] = []
        for raw_id in sorted(ids):
            aid = raw_id.decode("utf-8") if isinstance(raw_id, bytes) else str(raw_id)
            try:
                out.append(self.get_artifact(tenant_id=tenant_id, artifact_id=aid))
            except KeyError:
                continue
        return sorted(out, key=lambda a: a.version)

    def set_artifact_status(self, *, tenant_id: str, artifact_id: str, status: str) -> StoredArtifact:
        self._set_status(tenant_id=tenant_id, artifact_id=artifact_id, status=status)
        return self.get_artifact(tenant_id=tenant_id, artifact_id=artifact_id)

    def set_active_artifact(self, *, tenant_id: str, artifact_id: str) -> None:
        self.redis.set(_k(self.prefix, tenant_id, "ptr:active"), artifact_id)

    def get_active_artifact_id(self, *, tenant_id: str) -> str | None:
        v = self.redis.get(_k(self.prefix, tenant_id, "ptr:active"))
        if v is None:
            return None
        return v.decode("utf-8") if isinstance(v, bytes) else str(v)

    def set_previous_active_artifact(self, *, tenant_id: str, artifact_id: str | None) -> None:
        key = _k(self.prefix, tenant_id, "ptr:prev")
        if artifact_id is None:
            self.redis.delete(key)
        else:
            self.redis.set(key, artifact_id)

    def get_previous_active_artifact_id(self, *, tenant_id: str) -> str | None:
        v = self.redis.get(_k(self.prefix, tenant_id, "ptr:prev"))
        if v is None:
            return None
        return v.decode("utf-8") if isinstance(v, bytes) else str(v)

    def set_canary(self, *, tenant_id: str, artifact_id: str | None, weight: float | None) -> None:
        key = _k(self.prefix, tenant_id, "ptr:canary")
        if artifact_id is None:
            self.redis.delete(key)
            return
        self.redis.hset(key, mapping={"artifact_id": artifact_id, "weight": str(weight or 0.0)})

    def get_canary(self, *, tenant_id: str) -> CanaryConfig | None:
        key = _k(self.prefix, tenant_id, "ptr:canary")
        data = self.redis.hgetall(key) or {}
        if not data:
            return None
        def _s(v: Any) -> str:
            if isinstance(v, bytes):
                return v.decode("utf-8")
            return str(v)
        aid = _s(data.get(b"artifact_id") if b"artifact_id" in data else data.get("artifact_id"))
        weight = float(_s(data.get(b"weight") if b"weight" in data else data.get("weight")))
        return CanaryConfig(artifact_id=aid, weight=weight)

    def set_mode(self, *, tenant_id: str, mode: str) -> None:
        self.redis.set(_k(self.prefix, tenant_id, "ptr:mode"), mode)

    def get_mode(self, *, tenant_id: str) -> str:
        v = self.redis.get(_k(self.prefix, tenant_id, "ptr:mode"))
        if v is None:
            return "normal"
        return v.decode("utf-8") if isinstance(v, bytes) else str(v)

    def idempotency_get(self, *, tenant_id: str, key: str) -> dict[str, Any] | None:
        v = self.redis.get(_k(self.prefix, tenant_id, f"idem:{key}"))
        if v is None:
            return None
        raw = v.decode("utf-8") if isinstance(v, bytes) else str(v)
        return json.loads(raw)

    def idempotency_set(self, *, tenant_id: str, key: str, value: dict[str, Any], ttl_s: int) -> None:
        k = _k(self.prefix, tenant_id, f"idem:{key}")
        self.redis.set(k, json.dumps(value, separators=(",", ":"), sort_keys=True), ex=int(ttl_s))

    def audit_append(self, *, tenant_id: str, record: dict[str, Any]) -> None:
        self.redis.rpush(_k(self.prefix, tenant_id, "audit"), json.dumps(record, separators=(",", ":"), sort_keys=True))

    def audit_list(
        self, *, tenant_id: str, limit: int = 100, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        key = _k(self.prefix, tenant_id, "audit")
        start = int(cursor) if cursor else 0
        end = start + max(0, int(limit)) - 1
        raw = self.redis.lrange(key, start, end) or []
        items: list[dict[str, Any]] = []
        for row in raw:
            s = row.decode("utf-8") if isinstance(row, bytes) else str(row)
            items.append(json.loads(s))
        next_cursor = None
        if len(raw) == limit:
            next_cursor = str(start + limit)
        return items, next_cursor

    def metrics_incr(self, *, tenant_id: str, name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
        # Metrics are best-effort counters, stored in Redis.
        import json as _json
        labels = labels or {}
        label_key = _json.dumps(labels, separators=(",", ":"), sort_keys=True)
        key = _k(self.prefix, tenant_id, f"metric:{name}:{label_key}")
        try:
            self.redis.incrby(key, int(value))
        except Exception:
            # best-effort; swallow
            return

