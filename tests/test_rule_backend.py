"""Knowledge-base backend tests (offline deterministic explainer)."""

from pathlib import Path

from slither_chat.models import Finding, Severity
from slither_chat.rule_backend import KB, enrich, explain, explain_with_fields
from tests.conftest import load_fixture, vault_source, REPO
from slither_chat.parser import normalize


def _finding(rule_id: str, lines=(10, 11)) -> Finding:
    return Finding(
        rule_id=rule_id,
        description=f"{rule_id} description",
        impact="medium",
        confidence="Medium",
        severity=Severity.MEDIUM,
        contract="C",
        function="f",
        lines=list(lines),
    )


def test_kb_covers_major_detectors():
    for rule in ("reentrancy-eth", "tx-origin", "unchecked-lowlevel",
                 "divide-before-multiply", "weak-prng"):
        assert rule in KB


def test_explain_known_rule():
    text = explain(_finding("reentrancy-eth"))
    assert "checks-effects-interactions" in text
    assert "Why it matters" in text
    assert "Suggested fix" in text


def test_explain_unknown_rule_falls_back():
    text = explain(_finding("no-such-rule"))
    assert "{rule}" not in text  # placeholder was substituted
    assert "no-such-rule" in text


def test_explain_with_fields():
    what, fix = explain_with_fields(_finding("tx-origin"))
    assert "msg.sender" in fix
    assert what


def test_enrich_populates_fields(vault_payload, vault_source):
    from slither_chat.parser import normalize

    result = normalize(vault_payload, vault_source)
    enrich(result, vault_source)
    for f in result.findings:
        assert f.explanation
        assert f.fix
        assert f.patch
        assert f.source == "rule"
        assert "diff" in f.patch or "+++" in f.patch
    reent = next(f for f in result.findings if f.rule_id == "reentrancy-eth")
    assert "checks-effects-interactions" in reent.patch or "update" in reent.patch


def test_enrich_does_not_rewrite_severity(vault_payload, vault_source):
    from slither_chat.parser import normalize

    result = normalize(vault_payload, vault_source)
    before = {f.key: f.severity for f in result.findings}
    enrich(result, vault_source)
    after = {f.key: f.severity for f in result.findings}
    assert before == after