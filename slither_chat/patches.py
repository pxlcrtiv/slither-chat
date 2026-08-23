"""Generate ``diff``-style patch hints for flagged code regions.

slither-chat never claims to fully fix a contract: it pinpoints the exact
lines a detector flagged and produces a reviewable unified diff that (a)
marks the region and (b) shows a rule-specific hardening suggestion when the
knowledge base knows one. The output is a starting point for a human or an
LLM backend, not an autonomous fix.
"""

from __future__ import annotations

from pathlib import Path

from .models import Finding

_CONTEXT = 2


def build_patch(source_path: str | Path, finding: Finding, hint: str = "") -> str:
    """Return a unified diff annotating the flagged lines of a source file."""
    path = Path(source_path)
    try:
        text = path.read_text(errors="replace").splitlines()
    except OSError:
        return ""
    if not finding.lines:
        return ""

    lo = max(1, min(finding.lines) - _CONTEXT)
    hi = min(len(text), max(finding.lines) + _CONTEXT)
    marked = set(finding.lines)

    hunk = f"@@ -{lo},{hi - lo + 1} +{lo},{hi - lo + 1} @@"
    header = (
        f"--- a/{path.name}\n+++ b/{path.name}  (suggested hardening — review before applying)"
    )
    body = [hunk]
    for i in range(lo, hi + 1):
        prefix = "- " if i in marked else "  "
        body.append(f"{prefix}{i:>4} | {text[i - 1]}")
    if hint:
        body.append(f"+> {hint}")
    return header + "\n" + "\n".join(body) + "\n"


def inline_fix_hint(finding: Finding) -> str:
    """Short one-line hardening hint for a finding (used by rule backend)."""
    HINTS = {
        "reentrancy-eth": "apply checks-effects-interactions; update balances before external calls",
        "reentrancy-no-eth": "move state updates before external calls or add a reentrancy guard",
        "reentrancy-benign": "consider a reentrancy guard even for non-eth flows",
        "tx-origin": "use msg.sender instead of tx.origin for authorization",
        "arbitrary-send-eth": "never send ETH via arbitrary addresses; restrict to a allowlist",
        "controlled-delegatecall": "delegatecall only to pre-approved, immutable implementations",
        "unchecked-lowlevel": "check the return value of the low-level call and revert on failure",
        "unchecked-transfer": "check the transfer return value or use SafeERC20",
        "unchecked-send": "check the send return value and revert on failure",
        "dangerous-unary-unsigned": "guard integer reversal with an explicit edge-case check",
        "divide-before-multiply": "multiply before dividing to avoid precision loss",
        "weak-prng": "replace blockhash/block.timestamp randomness with a commit-reveal or oracle",
        "timestamp": "do not use block.timestamp as a source of strict equality or randomness",
        "incorrect-equality": "compare with a tolerance; strict equality on balances is fragile",
        "missing-zero-check": "revert on zero address during initialization",
        "uninitialized-state": "initialize storage variables or use a constructor initializer",
        "locked-ether": "add a withdraw function so received/remaining ETH is recoverable",
        "unused-state": "remove unused state variables to reduce gas and attack surface",
        "suicidal": "remove selfdestruct or gate it behind a timelock + multisig",
        "uniswap-reentrancy": "apply checks-effects-interactions around the uniswap call",
        "assembly": "avoid inline assembly; use idiomatic Solidity",
        "controlled-array-length": "validate the array length argument at the boundary",
        "constant-function-asm": "recompute values at construction, do not publish code",
        "constant-function-state": "remove state reads from a declared pure/constant function",
        "external-function": "prefer external visibility for public functions and reduce gas",
        "low-level-calls": "use high-level calls with try/catch instead of .call()",
        "calls-loop": "avoid external calls inside loops (gas griefing)",
        "reentrancy-events": "emit events after state mutation, before external calls",
    }
    return HINTS.get(
        finding.rule_id,
        "review the flagged lines; consult the detector docs for the canonical fix",
    )