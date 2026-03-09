"""MPC exception hierarchy."""
from __future__ import annotations

from typing import Any


class MPCError(Exception):
    """Base exception for all MPC errors."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class MPCValidationError(MPCError):
    """Raised when manifest validation fails."""

    def __init__(self, errors: list[Any]) -> None:
        self.errors = errors
        codes = ", ".join(getattr(e, "code", "?") for e in errors)
        super().__init__("E_VALID", f"Validation failed: {codes}")


class MPCBudgetError(MPCError):
    """Raised when an expression budget is exceeded."""

    def __init__(
        self, code: str, message: str, *, limit: int | None = None
    ) -> None:
        self.limit = limit
        super().__init__(code, message)
