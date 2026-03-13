from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Any
from mpc.features.workflow.persistence import StateStorePort

@dataclass
class JSONFileStateStore:
    """Persists workflow state to a local JSON file."""
    file_path: str
    _data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self):
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r", encoding="utf-8") as f:
                try:
                    self._data = json.load(f)
                except json.JSONDecodeError:
                    self._data = {}
        else:
            self._data = {}

    def _save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def save_state(self, instance_id: str, state_data: dict[str, Any]) -> None:
        if "states" not in self._data:
            self._data["states"] = {}
        self._data["states"][instance_id] = state_data
        self._save()

    def load_state(self, instance_id: str) -> dict[str, Any] | None:
        return self._data.get("states", {}).get(instance_id)

    def record_audit(self, instance_id: str, record_data: dict[str, Any]) -> None:
        if "audits" not in self._data:
            self._data["audits"] = {}
        if instance_id not in self._data["audits"]:
            self._data["audits"][instance_id] = []
        self._data["audits"][instance_id].append(record_data)
        self._save()

    def get_global_config(self, key: str) -> Any:
        return self._data.get("config", {}).get(key)

    def set_global_config(self, key: str, value: Any) -> None:
        if "config" not in self._data:
            self._data["config"] = {}
        self._data["config"][key] = value
        self._save()
