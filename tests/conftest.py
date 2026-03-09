from pathlib import Path

import pytest

from mpc.conformance.runner import ConformanceRunner

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_ROOT = REPO_ROOT / "packages" / "core-conformance" / "fixtures"
PRESETS_ROOT = REPO_ROOT / "packages" / "presets"
SCHEMAS_ROOT = REPO_ROOT / "packages" / "core-contracts" / "schemas"


@pytest.fixture()
def runner() -> ConformanceRunner:
    return ConformanceRunner(
        FIXTURES_ROOT, presets_root=PRESETS_ROOT, schemas_root=SCHEMAS_ROOT
    )
