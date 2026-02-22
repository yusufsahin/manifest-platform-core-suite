"""Run the normative conformance fixtures for implemented categories.

Every fixture in contracts/* and canonical/* MUST pass.
Unimplemented categories are skipped with a clear reason.
"""
import pytest
from pathlib import Path

from mpc.conformance.runner import ConformanceRunner

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_ROOT = REPO_ROOT / "packages" / "core-conformance" / "fixtures"


# ---------------------------------------------------------------------------
# contracts
# ---------------------------------------------------------------------------

class TestContractsConformance:
    @pytest.fixture(autouse=True)
    def _setup(self, runner: ConformanceRunner):
        self.runner = runner

    @pytest.mark.parametrize(
        "fixture_name",
        [d.name for d in sorted((FIXTURES_ROOT / "contracts").iterdir()) if d.is_dir()],
    )
    def test_fixture(self, fixture_name: str):
        result = self.runner.run_fixture(FIXTURES_ROOT / "contracts" / fixture_name)
        assert result.passed, (
            f"{result.fixture} FAILED\n"
            + "\n".join(result.diff)
            + "\n".join(result.violations)
        )


# ---------------------------------------------------------------------------
# canonical
# ---------------------------------------------------------------------------

class TestCanonicalConformance:
    @pytest.fixture(autouse=True)
    def _setup(self, runner: ConformanceRunner):
        self.runner = runner

    @pytest.mark.parametrize(
        "fixture_name",
        [d.name for d in sorted((FIXTURES_ROOT / "canonical").iterdir()) if d.is_dir()],
    )
    def test_fixture(self, fixture_name: str):
        result = self.runner.run_fixture(FIXTURES_ROOT / "canonical" / fixture_name)
        assert result.passed, (
            f"{result.fixture} FAILED\n"
            + "\n".join(result.diff)
            + "\n".join(result.violations)
        )


# ---------------------------------------------------------------------------
# all categories — smoke test
# ---------------------------------------------------------------------------

class TestRunAll:
    def test_implemented_categories_pass(self, runner: ConformanceRunner):
        results = runner.run_all()
        for r in results:
            if r.skipped:
                continue
            assert r.passed, (
                f"{r.fixture} FAILED\n"
                + "\n".join(r.diff)
                + "\n".join(r.violations)
            )

    def test_unimplemented_categories_skipped(self, runner: ConformanceRunner):
        results = runner.run_all()
        skipped = [r for r in results if r.skipped]
        assert len(skipped) > 0, "Expected some categories to be skipped"
        for r in skipped:
            assert r.skip_reason is not None
