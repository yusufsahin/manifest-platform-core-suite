from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tooling.mpc_runtime.authn import JwtPrincipal


@dataclass(frozen=True)
class ActorContext:
    tenant_id: str
    actor_id: str | None
    roles: set[str]


def context_from_jwt(principal: JwtPrincipal) -> ActorContext:
    claims = principal.claims
    tenant_id = str(claims.get("tenant_id") or claims.get("tid") or "").strip()
    if not tenant_id:
        raise ValueError("Missing tenant_id claim")
    actor_id = claims.get("sub") or claims.get("actor_id") or claims.get("oid")
    actor_id_str = str(actor_id) if actor_id is not None else None

    raw_roles: Any = claims.get("roles") or claims.get("role") or []
    roles: set[str] = set()
    if isinstance(raw_roles, str):
        roles = {r.strip() for r in raw_roles.split(",") if r.strip()}
    elif isinstance(raw_roles, list):
        roles = {str(r).strip() for r in raw_roles if str(r).strip()}
    else:
        roles = set()

    return ActorContext(tenant_id=tenant_id, actor_id=actor_id_str, roles=roles)

