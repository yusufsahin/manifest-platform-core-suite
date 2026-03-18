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
from dataclasses import dataclass, field, is_dataclass, asdict
from typing import Any
import traceback


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
        if is_dataclass(obj):
            # Convert to dict for easier walk/mutate
            obj_dict = asdict(obj)
            redacted_dict = self._walk(obj_dict, path)
            # We don't necessarily want to re-construct the dataclass here 
            # as it might be used for output/logging. Return the dict.
            return redacted_dict

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

    def redact_exception(self, e: Exception) -> str:
        """Mask sensitive keys in an exception traceback."""
        raw_trace = traceback.format_exc()
        # Simple line-based masking for demo purposes; in production use a more robust parser
        lines = raw_trace.splitlines()
        redacted_lines = []
        for line in lines:
            line_redacted = line
            for key in self.config.deny_keys:
                if f"{key}=" in line.lower() or f"'{key}':" in line.lower():
                    line_redacted = "[REDACTED TRACE LINE]"
                    break
            redacted_lines.append(line_redacted)
        return "\n".join(redacted_lines)

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
