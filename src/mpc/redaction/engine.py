"""Redaction engine — masks sensitive fields before output.

Per EPIC G1:
  - denyKeys: list of field paths that must always be masked
  - Applies to Trace, Error.details, log outputs, any dict
  - Deterministic: same input + same config = same output
  - Supports glob patterns for key matching (e.g., "*.password")
"""
from __future__ import annotations

import fnmatch
import copy
from dataclasses import dataclass, field
from typing import Any


_DEFAULT_MASK = "***"

_DEFAULT_DENY_KEYS: frozenset[str] = frozenset({
    "password",
    "secret",
    "token",
    "apiKey",
    "api_key",
    "authorization",
    "ssn",
    "creditCard",
    "credit_card",
})


@dataclass(frozen=True)
class RedactionConfig:
    """Configuration for the redaction engine."""
    deny_keys: frozenset[str] = _DEFAULT_DENY_KEYS
    deny_patterns: list[str] = field(default_factory=list)
    mask_value: str = _DEFAULT_MASK
    redact_null_values: bool = False


@dataclass
class RedactionEngine:
    """Mask sensitive fields in arbitrary data structures."""

    config: RedactionConfig = field(default_factory=RedactionConfig)

    def redact(self, data: Any) -> Any:
        """Return a deep copy of *data* with sensitive fields masked."""
        return self._walk(copy.deepcopy(data), "")

    def redact_in_place(self, data: Any) -> Any:
        """Redact *data* in place (mutates the input)."""
        return self._walk(data, "")

    def _walk(self, obj: Any, path: str) -> Any:
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                child_path = f"{path}.{key}" if path else key
                if self._should_redact(key, child_path):
                    if obj[key] is not None or self.config.redact_null_values:
                        obj[key] = self.config.mask_value
                else:
                    obj[key] = self._walk(obj[key], child_path)
            return obj

        if isinstance(obj, list):
            return [self._walk(item, f"{path}[]") for item in obj]

        return obj

    def _should_redact(self, key: str, full_path: str) -> bool:
        lower_key = key.lower()
        if lower_key in {k.lower() for k in self.config.deny_keys}:
            return True
        for pattern in self.config.deny_patterns:
            if fnmatch.fnmatch(full_path, pattern):
                return True
            if fnmatch.fnmatch(key, pattern):
                return True
        return False
