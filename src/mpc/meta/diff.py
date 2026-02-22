"""Breaking-change detection between two DomainMeta versions.

Breaking: removing a kind, adding a required prop, removing a type/function.
Non-breaking: adding a kind, adding an optional kind, adding a function.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from mpc.meta.models import DomainMeta


@dataclass
class MetaDiffResult:
    breaking: list[str] = field(default_factory=list)
    non_breaking: list[str] = field(default_factory=list)

    @property
    def has_breaking(self) -> bool:
        return len(self.breaking) > 0


def diff_meta(old: DomainMeta, new: DomainMeta) -> MetaDiffResult:
    """Compare *old* and *new* DomainMeta and classify changes."""
    result = MetaDiffResult()

    old_kinds = {k.name: k for k in old.kinds}
    new_kinds = {k.name: k for k in new.kinds}

    for name in old_kinds:
        if name not in new_kinds:
            result.breaking.append(f"Kind '{name}' removed")
        else:
            old_k, new_k = old_kinds[name], new_kinds[name]
            added_req = set(new_k.required_props) - set(old_k.required_props)
            for prop in sorted(added_req):
                result.breaking.append(
                    f"Kind '{name}': required property '{prop}' added"
                )
            removed_types = set(old_k.allowed_types) - set(new_k.allowed_types)
            for t in sorted(removed_types):
                result.breaking.append(
                    f"Kind '{name}': allowed type '{t}' removed"
                )

    for name in new_kinds:
        if name not in old_kinds:
            result.non_breaking.append(f"Kind '{name}' added")

    old_fns = {f.name for f in old.allowed_functions}
    new_fns = {f.name for f in new.allowed_functions}

    for fn in sorted(old_fns - new_fns):
        result.breaking.append(f"Function '{fn}' removed")
    for fn in sorted(new_fns - old_fns):
        result.non_breaking.append(f"Function '{fn}' added")

    old_types = set(old.allowed_types)
    new_types = set(new.allowed_types)
    for t in sorted(old_types - new_types):
        result.breaking.append(f"Global allowed type '{t}' removed")
    for t in sorted(new_types - old_types):
        result.non_breaking.append(f"Global allowed type '{t}' added")

    return result
