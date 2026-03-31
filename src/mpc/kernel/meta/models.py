"""DomainMeta — the consuming app's declaration of what constructs are valid.

Per MASTER_SPEC section 7:
  - allowed kinds and required properties
  - allowed types, events, functions (signature + cost)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mpc.kernel.meta.diff import MetaDiffResult


@dataclass(frozen=True)
class FunctionDef:
    name: str
    args: list[str] = field(default_factory=list)
    returns: str = "any"
    cost: int = 1


@dataclass(frozen=True)
class KindDef:
    name: str
    required_props: list[str] = field(default_factory=list)
    optional_props: list[str] = field(default_factory=list)
    allowed_types: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DomainMeta:
    schema_version: int = 1
    kinds: list[KindDef] = field(default_factory=list)
    allowed_types: list[str] = field(default_factory=list)
    allowed_events: list[str] = field(default_factory=list)
    allowed_functions: list[FunctionDef] = field(default_factory=list)

    def get_kind(self, name: str) -> KindDef | None:
        for k in self.kinds:
            if k.name == name:
                return k
        return None

    def get_function(self, name: str) -> FunctionDef | None:
        for f in self.allowed_functions:
            if f.name == name:
                return f
        return None

    @property
    def kind_names(self) -> frozenset[str]:
        return frozenset(k.name for k in self.kinds)

    @property
    def function_names(self) -> frozenset[str]:
        return frozenset(f.name for f in self.allowed_functions)


def diff_meta(old: DomainMeta, new: DomainMeta) -> "MetaDiffResult":
    """Backward-compatible import shim for mpc.kernel.meta.diff.diff_meta."""
    from mpc.kernel.meta.diff import diff_meta as _diff_meta

    return _diff_meta(old, new)
