from __future__ import annotations

import os

import pytest
import redis


def _redis_available() -> bool:
    url = os.environ.get("MPC_RUNTIME_REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.Redis.from_url(url, decode_responses=False)
        r.ping()
        return True
    except Exception:
        return False


def pytest_sessionstart(session: pytest.Session) -> None:
    # When running under release gate/CI, we want Redis-backed runtime tests to be real.
    require = str(os.environ.get("MPC_RUNTIME_REQUIRE_REDIS_TESTS", "")).lower() in ("1", "true", "yes")
    if require and not _redis_available():
        raise RuntimeError(
            "Redis is required for tooling/mpc-runtime/tests but is not reachable. "
            "Set MPC_RUNTIME_REDIS_URL or start a Redis service."
        )

