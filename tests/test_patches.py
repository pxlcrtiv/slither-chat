"""Patch snippet generator tests."""

from pathlib import Path

from slither_chat.models import Finding, Severity
from slither_chat.patches import build_patch, inline_fix_hint


def _src(tmp_path: Path) -> Path:
    p = tmp_path / "contract.sol"
    lines = [f"// line {i}" for i in range(1, 9)]
    lines[4] = "amount = amount;"
    p.write_text("\n".join(lines) + "\n")
    return p


def test_build_patch_marks_lines(tmp_path):
    p = _src(tmp_path)
    f = Finding(
        rule_id="reentrancy-eth",
        description="d",
        impact="high",
        confidence="High",
        severity=Severity.HIGH,
        lines=[5, 6],
    )
    patch = build_patch(p, f, hint="apply checks-effects-interactions")
    assert "--- a/contract.sol" in patch
    assert "+++ b/contract.sol" in patch
    assert "@@" in patch
    assert "- " in patch          # removal marker on flagged line
    assert "+> apply checks-effects-interactions" in patch
    # context lines rendered with their numbers
    assert "| // line 4" in patch


def test_build_patch_no_lines(tmp_path):
    p = _src(tmp_path)
    f = Finding(rule_id="x", description="d", impact="low",
                confidence="Low", severity=Severity.LOW, lines=[])
    assert build_patch(p, f) == ""


def test_build_patch_missing_file(tmp_path):
    f = Finding(rule_id="x", description="d", impact="low",
                confidence="Low", severity=Severity.LOW, lines=[1])
    assert build_patch(tmp_path / "missing.sol", f) == ""


def test_inline_fix_hint_known():
    f = Finding(rule_id="tx-origin", description="d", impact="medium",
                confidence="Medium", severity=Severity.MEDIUM)
    assert "msg.sender" in inline_fix_hint(f)


def test_inline_fix_hint_unknown():
    f = Finding(rule_id="brand-new-detector", description="d", impact="low",
                confidence="Low", severity=Severity.LOW)
    assert "review the flagged lines" in inline_fix_hint(f)