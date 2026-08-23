"""Normalization tests: slither JSON -> Findings (uses real captured fixture)."""

from slither_chat.models import AuditResult, Severity, severity_from_impact
from slither_chat.parser import normalize
from tests.conftest import REPO


def test_severity_mapping():
    assert severity_from_impact("High") is Severity.HIGH
    assert severity_from_impact("medium") is Severity.MEDIUM
    assert severity_from_impact("LOW") is Severity.LOW
    assert severity_from_impact("Informational") is Severity.INFORMATIONAL
    assert severity_from_impact("optimization") is Severity.INFORMATIONAL
    assert severity_from_impact("") is Severity.INFORMATIONAL
    assert severity_from_impact(None) is Severity.INFORMATIONAL


def test_normalize_finds_reentrancy(vault_payload, vault_source):
    result = normalize(vault_payload, vault_source)
    assert isinstance(result, AuditResult)
    rule_ids = [f.rule_id for f in result.findings]
    assert "reentrancy-eth" in rule_ids
    reent = next(f for f in result.findings if f.rule_id == "reentrancy-eth")
    assert reent.severity is Severity.HIGH
    assert reent.contract == "ReentrantVault"
    assert reent.lines  # flagged lines captured
    assert "balances" in reent.code  # code snippet pulled from the real file


def test_normalize_dedup(vault_payload, vault_source):
    result = normalize(vault_payload, vault_source)
    keys = [f.key for f in result.findings]
    assert len(keys) == len(set(keys)), "duplicate findings must be removed"


def test_sorted_order(vault_payload, vault_source):
    result = normalize(vault_payload, vault_source)
    ordered = result.sorted()
    sevs = [f.severity for f in ordered]
    ranks = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2, Severity.INFORMATIONAL: 3}
    assert ranks[sevs[0]] <= ranks[sevs[len(sevs) // 2]] <= ranks[sevs[-1]]


def test_snippet_marks_flag_lines(vault_payload, vault_source):
    result = normalize(vault_payload, vault_source)
    reent = next(f for f in result.findings if f.rule_id == "reentrancy-eth")
    flagged = {l for l in reent.lines if l in range(1, 200)}
    assert flagged, "snippet must contain flagged lines"
    # snippet lines look like ">> N | source"
    assert any(line.startswith(">>") for line in reent.code.splitlines())


def test_location_string(vault_payload, vault_source):
    result = normalize(vault_payload, vault_source)
    reent = next(f for f in result.findings if f.rule_id == "reentrancy-eth")
    assert reent.location == "ReentrantVault:withdraw"


def test_empty_payload():
    result = normalize({"results": {}}, "nope.sol")
    assert result.findings == []
    assert result.by_severity()["High"] == 0


def test_fixture_is_committed():
    # the captured fixture lives in the repo so parser tests run offline
    assert (REPO / "tests" / "fixtures" / "slither_vault.json").exists()