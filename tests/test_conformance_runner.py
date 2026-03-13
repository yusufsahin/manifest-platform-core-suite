"""Run the normative conformance fixtures for implemented categories.

Every fixture in contracts/*, canonical/*, and workflow/* MUST pass.
Unimplemented categories are skipped with a clear reason.
Security (PII) fixtures are out of scope and removed; see docs/SCOPE.md.
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
# workflow
# ---------------------------------------------------------------------------

class TestWorkflowConformance:
    @pytest.fixture(autouse=True)
    def _setup(self, runner: ConformanceRunner):
        self.runner = runner

    @pytest.mark.parametrize(
        "fixture_name",
        [d.name for d in sorted((FIXTURES_ROOT / "workflow").iterdir()) if d.is_dir()],
    )
    def test_fixture(self, fixture_name: str):
        result = self.runner.run_fixture(FIXTURES_ROOT / "workflow" / fixture_name)
        assert result.passed, (
            f"{result.fixture} FAILED\n"
            + "\n".join(result.diff)
            + "\n".join(result.violations)
        )


# ---------------------------------------------------------------------------
# expr
# ---------------------------------------------------------------------------

class TestExprConformance:
    @pytest.fixture(autouse=True)
    def _setup(self, runner: ConformanceRunner):
        self.runner = runner

    @pytest.mark.parametrize(
        "fixture_name",
        [d.name for d in sorted((FIXTURES_ROOT / "expr").iterdir()) if d.is_dir()],
    )
    def test_fixture(self, fixture_name: str):
        result = self.runner.run_fixture(FIXTURES_ROOT / "expr" / fixture_name)
        assert result.passed, (
            f"{result.fixture} FAILED\n"
            + "\n".join(result.diff)
            + "\n".join(result.violations)
        )


# ---------------------------------------------------------------------------
# acl
# ---------------------------------------------------------------------------

class TestAclConformance:
    @pytest.fixture(autouse=True)
    def _setup(self, runner: ConformanceRunner):
        self.runner = runner

    @pytest.mark.parametrize(
        "fixture_name",
        [d.name for d in sorted((FIXTURES_ROOT / "acl").iterdir()) if d.is_dir()],
    )
    def test_fixture(self, fixture_name: str):
        result = self.runner.run_fixture(FIXTURES_ROOT / "acl" / fixture_name)
        assert result.passed, (
            f"{result.fixture} FAILED\n"
            + "\n".join(result.diff)
            + "\n".join(result.violations)
        )


# ---------------------------------------------------------------------------
# policy
# ---------------------------------------------------------------------------

class TestPolicyConformance:
    @pytest.fixture(autouse=True)
    def _setup(self, runner: ConformanceRunner):
        self.runner = runner

    @pytest.mark.parametrize(
        "fixture_name",
        [d.name for d in sorted((FIXTURES_ROOT / "policy").iterdir()) if d.is_dir()],
    )
    def test_fixture(self, fixture_name: str):
        result = self.runner.run_fixture(FIXTURES_ROOT / "policy" / fixture_name)
        assert result.passed, (
            f"{result.fixture} FAILED\n"
            + "\n".join(result.diff)
            + "\n".join(result.violations)
        )


# ---------------------------------------------------------------------------
# compose
# ---------------------------------------------------------------------------

class TestComposeConformance:
    @pytest.fixture(autouse=True)
    def _setup(self, runner: ConformanceRunner):
        self.runner = runner

    @pytest.mark.parametrize(
        "fixture_name",
        [d.name for d in sorted((FIXTURES_ROOT / "compose").iterdir()) if d.is_dir()],
    )
    def test_fixture(self, fixture_name: str):
        result = self.runner.run_fixture(FIXTURES_ROOT / "compose" / fixture_name)
        assert result.passed, (
            f"{result.fixture} FAILED\n"
            + "\n".join(result.diff)
            + "\n".join(result.violations)
        )


# ---------------------------------------------------------------------------
# overlay
# ---------------------------------------------------------------------------

class TestOverlayConformance:
    @pytest.fixture(autouse=True)
    def _setup(self, runner: ConformanceRunner):
        self.runner = runner

    @pytest.mark.parametrize(
        "fixture_name",
        [d.name for d in sorted((FIXTURES_ROOT / "overlay").iterdir()) if d.is_dir()],
    )
    def test_fixture(self, fixture_name: str):
        result = self.runner.run_fixture(FIXTURES_ROOT / "overlay" / fixture_name)
        assert result.passed, (
            f"{result.fixture} FAILED\n"
            + "\n".join(result.diff)
            + "\n".join(result.violations)
        )


# ---------------------------------------------------------------------------
# governance
# ---------------------------------------------------------------------------

class TestGovernanceConformance:
    @pytest.fixture(autouse=True)
    def _setup(self, runner: ConformanceRunner):
        self.runner = runner

    @pytest.mark.parametrize(
        "fixture_name",
        [d.name for d in sorted((FIXTURES_ROOT / "governance").iterdir()) if d.is_dir()],
    )
    def test_fixture(self, fixture_name: str):
        result = self.runner.run_fixture(FIXTURES_ROOT / "governance" / fixture_name)
        assert result.passed, (
            f"{result.fixture} FAILED\n"
            + "\n".join(result.diff)
            + "\n".join(result.violations)
        )


# ---------------------------------------------------------------------------
# evaluate_integration
# ---------------------------------------------------------------------------

class TestEvaluateIntegrationConformance:
    @pytest.fixture(autouse=True)
    def _setup(self, runner: ConformanceRunner):
        self.runner = runner

    @pytest.mark.parametrize(
        "fixture_name",
        [d.name for d in sorted((FIXTURES_ROOT / "evaluate_integration").iterdir()) if d.is_dir()],
    )
    def test_fixture(self, fixture_name: str):
        result = self.runner.run_fixture(FIXTURES_ROOT / "evaluate_integration" / fixture_name)
        assert result.passed, (
            f"{result.fixture} FAILED\n"
            + "\n".join(result.diff)
            + "\n".join(result.violations)
        )


# ---------------------------------------------------------------------------
# validator
# ---------------------------------------------------------------------------

class TestValidatorConformance:
    @pytest.fixture(autouse=True)
    def _setup(self, runner: ConformanceRunner):
        self.runner = runner

    @pytest.mark.parametrize(
        "fixture_name",
        [d.name for d in sorted((FIXTURES_ROOT / "validator").iterdir()) if d.is_dir()],
    )
    def test_fixture(self, fixture_name: str):
        result = self.runner.run_fixture(FIXTURES_ROOT / "validator" / fixture_name)
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
        """If any category has no handler, those fixtures are skipped with a reason."""
        results = runner.run_all()
        skipped = [r for r in results if r.skipped]
        for r in skipped:
            assert r.skip_reason is not None, f"Fixture {r.fixture} skipped without reason"
