"""Stable hashing via canonical JSON."""
from __future__ import annotations

import hashlib
from typing import Any

from mpc.kernel.canonical.serializer import canonicalize_bytes


def stable_hash(obj: Any, *, algorithm: str = "sha256") -> str:
    """Compute a stable hex digest over the canonical JSON form of *obj*."""
    return hashlib.new(algorithm, canonicalize_bytes(obj)).hexdigest()
