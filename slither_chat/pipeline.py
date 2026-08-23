"""End-to-end audit pipeline: analyze -> normalize -> enrich -> report."""

from __future__ import annotations

from pathlib import Path

from .analyzer import run_slither
from .models import AuditResult
from .parser import normalize


def audit(
    source: str | Path,
    backend: str = "rule",
    hf_model: str | None = None,
    llm_client=None,
) -> AuditResult:
    """Run slither, normalize, and enrich with the chosen backend.

    backend:
      rule  — deterministic knowledge base (default, offline)
      hf    — HF zero-shot vulnerability-class tagging on CPU (downloads model once)
      llm   — OpenAI-compatible explainer (needs LLM_BASE_URL + LLM_API_KEY)
    """
    from . import llm_backend, rule_backend  # light imports

    payload = run_slither(Path(source))
    result = normalize(payload, Path(source))

    if backend == "rule":
        rule_backend.enrich(result, Path(source))
        result.backend = "rule"
    elif backend == "hf":
        from .hf_enrich import enrich_with_hf

        enrich_with_hf(result, Path(source), hf_model=hf_model)
        result.backend = "hf"
    elif backend == "llm":
        llm_backend.LLMExplainer(client=llm_client).enrich(result, Path(source))
        result.backend = "llm"
    else:
        raise ValueError(f"unknown backend: {backend!r} (expected rule|hf|llm)")

    return result