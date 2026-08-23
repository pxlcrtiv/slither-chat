"""Deterministic, offline explainer backend.

Zero network, zero model: explains every Slither detector from a curated
knowledge base (KB). Used as the default backend and as the fallback for the
LLM/HF backends when they are unavailable — the agent-lab "mock backend"
pattern, so the whole pipeline runs anywhere.
"""

from __future__ import annotations

from pathlib import Path

from .models import Finding
from .patches import build_patch, inline_fix_hint

#: rule_id -> (what it is, why it matters, how to fix it)
KB: dict[str, tuple[str, str, str]] = {
    "reentrancy-eth": (
        "External call into an untrusted contract before state is updated",
        "An attacker contract can re-enter the function and drain funds because "
        "the balance/state is still the pre-update value. This is the classic "
        "DAO-hack class of bug.",
        "Apply checks-effects-interactions: update all state (including balances) "
        "before making the external call, or use a reentrancy guard modifier.",
    ),
    "reentrancy-no-eth": (
        "External call can be re-entered (no ETH involved)",
        "Same re-entry risk, but without an immediate ETH transfer — usually "
        "token transfers or callbacks can still be exploited.",
        "Move state mutations before the external call and add a guard modifier.",
    ),
    "tx-origin": (
        "Authorization uses tx.origin instead of msg.sender",
        "tx.origin is the original EOA that signed the transaction. A victim "
        "calling ANY contract in the call chain makes that contract authorize "
        "your calls — phishing contracts can borrow your identity.",
        "Replace tx.origin checks with msg.sender, which is the direct caller.",
    ),
    "arbitrary-send-eth": (
        "ETH is sent to an address that is not constrained",
        "If an attacker can influence the recipient (e.g. from storage or calldata), "
        "funds can be stolen via a malicious target.",
        "Restrict recipients to an allowlist or pre-verified addresses.",
    ),
    "controlled-delegatecall": (
        "delegatecall targets an address that can be influenced by the caller",
        "delegatecall runs the target's code in THIS contract's context — a "
        "malicious target can rewrite storage or steal funds.",
        "Only delegatecall to immutable, pre-deployed implementations you control, "
        "ideally stored in a constant.",
    ),
    "unchecked-lowlevel": (
        "Low-level call without checking success",
        "A failed call is silently swallowed; the caller continues with stale "
        "state and users can lose funds without any error surfacing.",
        "Check the returned bool and revert on failure (or use require).",
    ),
    "unchecked-transfer": (
        "ERC20 transfer return value is not checked",
        "Some tokens (USDT-style) return false instead of reverting; the "
        "transfer silently failed but the caller assumes success.",
        "Require the transfer to return true, or use OpenZeppelin SafeERC20.",
    ),
    "divide-before-multiply": (
        "Division is performed before multiplication",
        "Integer division truncates; multiplying afterwards keeps the truncation "
        "error and can cause large precision loss in token math.",
        "Perform multiplication first, then divide.",
    ),
    "weak-prng": (
        "Randomness derived from blockhash/block.timestamp",
        "Miners/validators can influence blockhash and timestamp to bias the "
        "outcome, breaking fairness (lotteries, NFTs, games).",
        "Use a commit-reveal scheme, a VRF oracle (Chainlink), or an external "
        "randomness service.",
    ),
    "timestamp": (
        "Dangerous use of block.timestamp",
        "Strict equality or randomness from block.timestamp can be manipulated "
        "by miners within a few seconds, breaking time-based logic.",
        "Use block.timestamp only for coarse time windows; never for equality "
        "checks or randomness.",
    ),
    "incorrect-equality": (
        "Strict equality used on a value that can be skewed",
        "Balances and price-derived values can deviate by a few wei; strict "
        "equality checks are fragile and can be DoS'd.",
        "Compare with a tolerance range (>= / <= thresholds).",
    ),
    "missing-zero-check": (
        "Address parameter can be set to address(0)",
        "Zero-address assignments permanently burn assets or break admin paths.",
        "require(param != address(0)) in constructors and setters.",
    ),
    "uninitialized-state": (
        "Storage variable not initialized",
        "Uninitialized variables hold zero/garbage values that can be used in "
        "unsafe ways before setup.",
        "Initialize in the constructor or with an explicit initializer.",
    ),
    "locked-ether": (
        "Contract can receive ETH but has no withdraw path",
        "ETH accepted via receive/fallback is stuck forever — user funds can "
        "be unrecoverable.",
        "Add a withdraw/claim function (or a sweep with an owner restriction).",
    ),
    "suicidal": (
        "selfdestruct can be invoked by an untrusted path",
        "selfdestruct destroys the contract and force-sends its balance.",
        "Remove selfdestruct or gate it behind multisig + timelock.",
    ),
    "calls-loop": (
        "External calls inside a loop",
        "Each iteration pays for a call and can re-enter; a malicious callee "
        "can DoS the whole loop.",
        "Use pull-over-push (let users withdraw individually).",
    ),
    "low-level-calls": (
        "Preference of low-level calls over high-level Solidity calls",
        "Low-level calls bypass checks and return raw bools; they hide errors "
        "and enable subtle bugs.",
        "Use high-level calls with try/catch.",
    ),
    "constant-function-asm": (
        "Assembly block disables compiler optimizations",
        "Raw assembly can break the optimizer's assumptions and introduce "
        "opcode-level bugs.",
        "Avoid assembly unless strictly necessary; document invariants.",
    ),
    "assembly": (
        "Use of inline assembly",
        "Assembly is hard to audit; a single wrong opcode can be a critical "
        "vulnerability.",
        "Prefer idiomatic Solidity; isolate and document any required assembly.",
    ),
    "external-function": (
        "Public function could be declared external",
        "Gas inefficiency (public copies args to memory).",
        "Declare the function external.",
    ),
    "unused-state": (
        "State variable is never used",
        "Dead storage wastes gas and can confuse audits.",
        "Remove the variable (or use it).",
    ),
    "uninitialized-local": (
        "Local variable not initialized",
        "Locals default to zero; using them before assignment can silently "
        "produce wrong values.",
        "Initialize locals at declaration.",
    ),
    "controlled-array-length": (
        "Array length from calldata can be very large",
        "An attacker can force huge loops over the length, DoSing the function "
        "or triggering OOG.",
        "Validate/cap the length at the function boundary.",
    ),
    "reentrancy-events": (
        "Events emitted before state updates in a reentrant path",
        "Event ordering can mislead indexers and wallets' balance displays "
        "during re-entrant calls.",
        "Emit events after state mutations.",
    ),
    "uniswap-reentrancy": (
        "Reentrancy through the Uniswap pair callback",
        "Uniswap's nonReentrant guard only covers the pair; your surrounding "
        "logic can still be re-entered via callbacks.",
        "Apply checks-effects-interactions and guards around the swap call.",
    ),
}

_FALLBACK = (
    "A Slither detector ({rule}) flagged this code — see the detector "
    "documentation for the canonical explanation.",
    "Static-analysis rules flag patterns that correlate with real exploits; "
    "treat every finding as actionable until proven benign.",
    "Review the flagged lines; add explicit guards or refactor the pattern "
    "the detector describes.",
)


def explain(finding: Finding) -> str:
    what, why, fix = KB.get(finding.rule_id, _FALLBACK)
    if finding.rule_id not in KB:
        what = what.format(rule=finding.rule_id)
    return f"{what}.\n\nWhy it matters: {why}\n\nSuggested fix: {fix}"


def explain_with_fields(finding: Finding) -> tuple[str, str]:
    what, why, fix = KB.get(finding.rule_id, _FALLBACK)
    if finding.rule_id not in KB:
        what = what.format(rule=finding.rule_id)
    return f"{what}. {why}", fix


def enrich(result, source_path: str | Path) -> None:
    """Fill explanation/fix/patch on every finding (in place)."""
    for f in result.findings:
        f.explanation, f.fix = explain_with_fields(f)
        f.patch = build_patch(source_path, f, hint=inline_fix_hint(f))
        f.source = "rule"