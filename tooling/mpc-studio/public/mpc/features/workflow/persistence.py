"""Persistence layer for Workflow Engine.

Defines ports for state storage and provides default adapters.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
import json
import time

@runtime_checkable
class StateStorePort(Protocol):
    """Interface for persisting workflow state."""
    def save_state(self, instance_id: str, state_data: dict[str, Any]) -> None: ...
    def load_state(self, instance_id: str) -> dict[str, Any] | None: ...
    def record_audit(self, instance_id: str, record_data: dict[str, Any]) -> None: ...

@dataclass
class InMemoryStateStore:
    """Simple in-memory store for testing."""
    _states: dict[str, dict[str, Any]] = field(default_factory=dict)
    _audits: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def save_state(self, instance_id: str, state_data: dict[str, Any]) -> None:
        self._states[instance_id] = state_data

    def load_state(self, instance_id: str) -> dict[str, Any] | None:
        return self._states.get(instance_id)

    def record_audit(self, instance_id: str, record_data: dict[str, Any]) -> None:
        if instance_id not in self._audits:
            self._audits[instance_id] = []
        self._audits[instance_id].append(record_data)

class SqlAlchemyStateStore:
    """SQLAlchemy-based state store adapter.
    
    Expects a repository-like object that handles the actual DB session logic.
    """
    def __init__(self, repository: Any) -> None:
        self._repo = repository

    async def save_state(self, instance_id: str, state_data: dict[str, Any]) -> None:
        # Map engine state to DB instance model
        # instance_id here is usually the DB primary key
        await self._repo.save_instance({
            "id": instance_id,
            "active_states": state_data.get("active_states", []),
            "variables": state_data.get("variables", {}),
            "is_active": state_data.get("is_active", True)
        })

    async def load_state(self, instance_id: str) -> dict[str, Any] | None:
        data = await self._repo.get_instance_by_entity_id(instance_id) # Simplified, usually entity+type
        if not data: return None
        return {
            "active_states": data.get("active_states"),
            "is_active": data.get("is_active"),
            "variables": data.get("variables")
        }

    async def record_audit(self, instance_id: str, record_data: dict[str, Any]) -> None:
        await self._repo.add_audit({
            "instance_id": instance_id,
            **record_data
        })
