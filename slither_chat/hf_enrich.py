"""Wrapper so ``--backend hf`` has one entry point (keeps pipeline.py slim)."""

from __future__ import annotations

from pathlib import Path

from .hf_backend import _MODEL_ID, ZeroShotVulnClassifier
from .models import AuditResult
from .rule_backend import enrich as rule_enrich


def enrich_with_hf(
    result: AuditResult, source_path: str | Path, hf_model: str | None = None
) -> None:
    """Rule explanations + on-device HF vulnerability-class tagging."""
    rule_enrich(result, source_path)
    classifier = ZeroShotVulnClassifier(model_id=hf_model or _MODEL_ID)
    classifier.enrich(result, source_path)