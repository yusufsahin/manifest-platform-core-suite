"""CLI entry point for the conformance runner.

Usage:
    python -m mpc.conformance run <fixtures-root> [--category <name>]
    python -m mpc.conformance run <fixtures-root> [--presets <path>] [--schemas <path>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mpc.tooling.conformance.runner import ConformanceRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mpc-conformance",
        description="Run MPC conformance fixture packs.",
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Execute conformance fixtures")
    run_parser.add_argument("fixtures", type=Path, help="Path to fixtures root")
    run_parser.add_argument("--presets", type=Path, default=None)
    run_parser.add_argument("--schemas", type=Path, default=None)
    run_parser.add_argument("--category", type=str, default=None,
                            help="Run only this category")

    args = parser.parse_args(argv)

    if args.command != "run":
        parser.print_help()
        return 1

    runner = ConformanceRunner(
        args.fixtures,
        presets_root=args.presets,
        schemas_root=args.schemas,
    )

    if args.category:
        results = runner.run_category(args.category)
    else:
        results = runner.run_all()

    passed = sum(1 for r in results if r.passed)
    skipped = sum(1 for r in results if r.skipped)
    failed = sum(1 for r in results if not r.passed and not r.skipped)

    for r in results:
        if r.passed:
            print(f"  PASS  {r.fixture}")
        elif r.skipped:
            print(f"  SKIP  {r.fixture} ({r.skip_reason})")
        else:
            print(f"  FAIL  {r.fixture}")
            for d in r.diff:
                print(f"        {d}")
            for v in r.violations:
                print(f"        VIOLATION: {v}")
            for t in r.trace:
                print(f"        TRACE: {t}")

    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
