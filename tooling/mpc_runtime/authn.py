from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuthnConfig:
    mode: str  # "header" | "jwt"
    issuer: str | None = None
    audience: str | None = None
    jwks_url: str | None = None
    jwks_json: dict[str, Any] | None = None
    jwks_cache_ttl_s: int = 300


@dataclass(frozen=True)
class JwtPrincipal:
    claims: dict[str, Any]


class JWKSCache:
    def __init__(self) -> None:
        self._value: dict[str, Any] | None = None
        self._fetched_at: float = 0.0
        self._source: str | None = None

    def get(self, *, source: str, ttl_s: int) -> dict[str, Any] | None:
        if self._value is None:
            return None
        if self._source != source:
            return None
        if (time.time() - self._fetched_at) > ttl_s:
            return None
        return self._value

    def set(self, *, source: str, jwks: dict[str, Any]) -> None:
        self._value = jwks
        self._fetched_at = time.time()
        self._source = source


_JWKS_CACHE = JWKSCache()


def parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _fetch_jwks(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=3) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def load_jwks(cfg: AuthnConfig) -> dict[str, Any] | None:
    if cfg.jwks_json is not None:
        return cfg.jwks_json
    if not cfg.jwks_url:
        return None
    cached = _JWKS_CACHE.get(source=cfg.jwks_url, ttl_s=int(cfg.jwks_cache_ttl_s))
    if cached is not None:
        return cached
    jwks = _fetch_jwks(cfg.jwks_url)
    _JWKS_CACHE.set(source=cfg.jwks_url, jwks=jwks)
    return jwks


def verify_jwt(*, token: str, cfg: AuthnConfig) -> JwtPrincipal:
    import jwt

    jwks = load_jwks(cfg)
    if not jwks:
        raise ValueError("JWKS not configured")

    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise ValueError("Missing kid")

    # Resolve key from JWKS (RSA only for now)
    keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
    key_obj = None
    for k in keys:
        if isinstance(k, dict) and k.get("kid") == kid:
            key_obj = k
            break
    if not key_obj:
        raise ValueError(f"Unknown kid '{kid}'")

    from jwt.algorithms import RSAAlgorithm

    public_key = RSAAlgorithm.from_jwk(json.dumps(key_obj, separators=(",", ":"), sort_keys=True))
    options = {"verify_aud": bool(cfg.audience)}
    claims = jwt.decode(
        token,
        key=public_key,
        algorithms=["RS256"],
        issuer=cfg.issuer if cfg.issuer else None,
        audience=cfg.audience if cfg.audience else None,
        options=options,
    )
    return JwtPrincipal(claims=dict(claims))

