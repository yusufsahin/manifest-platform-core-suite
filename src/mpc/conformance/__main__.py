"""Backward-compatible CLI entry point for conformance runner."""

from mpc.tooling.conformance.__main__ import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
