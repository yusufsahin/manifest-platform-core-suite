"""Breaking-change detection between two DomainMeta versions.

Breaking: removing a kind, adding a required prop, removing a type/function,
          changing function signature, removing an event.
Non-breaking: adding a kind, adding an optional kind, adding a function/event.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from mpc.meta.models import DomainMeta, FunctionDef


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

    _diff_kinds(old, new, result)
    _diff_functions(old, new, result)
    _diff_types(old, new, result)
    _diff_events(old, new, result)

    return result


def _diff_kinds(old: DomainMeta, new: DomainMeta, result: MetaDiffResult) -> None:
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


def _diff_functions(old: DomainMeta, new: DomainMeta, result: MetaDiffResult) -> None:
    old_fns = {f.name: f for f in old.allowed_functions}
    new_fns = {f.name: f for f in new.allowed_functions}

    for fn_name in sorted(set(old_fns) - set(new_fns)):
        result.breaking.append(f"Function '{fn_name}' removed")

    for fn_name in sorted(set(new_fns) - set(old_fns)):
        result.non_breaking.append(f"Function '{fn_name}' added")

    for fn_name in sorted(set(old_fns) & set(new_fns)):
        old_f = old_fns[fn_name]
        new_f = new_fns[fn_name]
        changes = _compare_function_sig(old_f, new_f)
        for change in changes:
            result.breaking.append(f"Function '{fn_name}': {change}")


def _compare_function_sig(old: FunctionDef, new: FunctionDef) -> list[str]:
    changes: list[str] = []
    if old.args != new.args:
        changes.append(f"args changed from {old.args} to {new.args}")
    if old.returns != new.returns:
        changes.append(f"return type changed from '{old.returns}' to '{new.returns}'")
    if old.cost != new.cost:
        changes.append(f"cost changed from {old.cost} to {new.cost}")
    return changes


def _diff_types(old: DomainMeta, new: DomainMeta, result: MetaDiffResult) -> None:
    old_types = set(old.allowed_types)
    new_types = set(new.allowed_types)
    for t in sorted(old_types - new_types):
        result.breaking.append(f"Global allowed type '{t}' removed")
    for t in sorted(new_types - old_types):
        result.non_breaking.append(f"Global allowed type '{t}' added")


def _diff_events(old: DomainMeta, new: DomainMeta, result: MetaDiffResult) -> None:
    old_events = set(old.allowed_events)
    new_events = set(new.allowed_events)
    for ev in sorted(old_events - new_events):
        result.breaking.append(f"Allowed event '{ev}' removed")
    for ev in sorted(new_events - old_events):
        result.non_breaking.append(f"Allowed event '{ev}' added")
