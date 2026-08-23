"""End-to-end integration: the shipped example contracts must be flagged with
the vulnerabilities they document. Runs real slither + solc (CI installs both).
"""

import pytest

from slither_chat.analyzer import run_slither
from slither_chat.parser import normalize
from tests.conftest import requires_solc

pytestmark = pytest.mark.slow


def _audit(path):
    payload = run_slither(path)
    result = normalize(payload, path)
    return {f.rule_id for f in result.findings}


@pytest.mark.parametrize(
    "name,expected",
    [
        ("vault", {"reentrancy-eth", "calls-loop"}),
        ("gateway", {"tx-origin", "arbitrary-send-eth", "missing-zero-check"}),
        ("oracle", {"divide-before-multiply", "timestamp"}),
    ],
)
def test_example_contracts_flagged(example_paths, name, expected):
    requires_solc()
    found = _audit(example_paths[name])
    missing = expected - found
    assert not missing, f"{name}.sol missing detectors: {missing} (found {found})"


def test_all_examples_parse_without_error(example_paths):
    requires_solc()
    for name, path in example_paths.items():
        result = normalize(run_slither(path), path)
        assert result.findings, f"{name}.sol produced no findings"