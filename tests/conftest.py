"""Shared pytest plumbing: paths, fixture loading, example contracts."""

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = REPO / "examples"
FIXTURES = REPO / "tests" / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(scope="session")
def vault_payload() -> dict:
    return load_fixture("slither_vault.json")


@pytest.fixture(scope="session")
def vault_source() -> Path:
    return EXAMPLES / "vault.sol"


@pytest.fixture(scope="session")
def example_paths() -> dict[str, Path]:
    return {
        "vault": EXAMPLES / "vault.sol",
        "gateway": EXAMPLES / "gateway.sol",
        "oracle": EXAMPLES / "oracle.sol",
    }


def requires_solc():
    """Skip when no solc binary is available (CI installs it)."""
    import shutil

    if shutil.which("solc"):
        return
    # solc-select layouts
    for p in (Path.home() / ".solc-select" / "artifacts").glob("solc-*/solc-*"):
        if p.is_file():
            return
    pytest.skip("solc not found on PATH")