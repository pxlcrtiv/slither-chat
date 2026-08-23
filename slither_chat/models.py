"""Core data models for slither-chat.

A normalized representation of Slither's JSON output that all backends
(rule-based, Hugging Face, LLM) and renderers operate on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    """Severity levels, ordered High -> Informational."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFORMATIONAL = "Informational"


#: Rank used for ordering (High = 0 is "most severe").
def _rank(sev: Severity) -> int:
    return {
        Severity.HIGH: 0,
        Severity.MEDIUM: 1,
        Severity.LOW: 2,
        Severity.INFORMATIONAL: 3,
    }[sev]

SEVERITY_ORDER = [Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFORMATIONAL]

# Slither "impact" values -> our severity scale.
IMPACT_MAP = {
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "informational": Severity.INFORMATIONAL,
    "optimization": Severity.INFORMATIONAL,
    "organization": Severity.INFORMATIONAL,
    "": Severity.INFORMATIONAL,
}

CONFIDENCE_KEYS = {"high", "medium", "low"}


def severity_from_impact(impact: str | None) -> Severity:
    return IMPACT_MAP.get((impact or "").strip().lower(), Severity.INFORMATIONAL)


@dataclass
class Finding:
    """One flagged issue, normalized from a Slither detector result."""

    rule_id: str
    description: str
    impact: str
    confidence: str
    severity: Severity = Severity.INFORMATIONAL
    contract: str = ""
    function: str = ""
    lines: list[int] = field(default_factory=list)
    code: str = ""
    evidence: str = ""
    explanation: str = ""
    fix: str = ""
    patch: str = ""
    issue_class: str = ""     # HF zero-shot class tag (backend=hf)
    class_confidence: float = 0.0
    source: str = ""  # backend that produced explanation: rule | hf | llm

    @property
    def key(self) -> tuple:
        """Identity used for deduplication."""
        return (self.rule_id, tuple(sorted(self.lines)))

    @property
    def location(self) -> str:
        parts = [p for p in (self.contract, self.function) if p]
        return ":".join(parts) if parts else "-"


@dataclass
class AuditResult:
    """Everything the pipeline produced for one audit."""

    source_path: str
    findings: list[Finding] = field(default_factory=list)
    slither_version: str = ""
    compiler: str = ""
    duration_sec: float = 0.0
    warnings: list[str] = field(default_factory=list)
    backend: str = "rule"

    @property
    def high(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.HIGH]

    @property
    def medium(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.MEDIUM]

    @property
    def low(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.LOW]

    @property
    def informational(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.INFORMATIONAL]

    def by_severity(self) -> dict[str, int]:
        counts = {s.value: 0 for s in SEVERITY_ORDER}
        for f in self.findings:
            counts[f.severity.value] += 1
        return counts

    def sorted(self) -> list[Finding]:
        return sorted(
            self.findings,
            key=lambda f: (_rank(f.severity), f.contract, f.function),
        )


class AnalysisError(Exception):
    """Raised when the underlying Slither run fails."""