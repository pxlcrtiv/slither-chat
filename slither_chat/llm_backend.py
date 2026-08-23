"""LLM explainer backend (OpenAI-compatible chat API).

Provider-agnostic: point it at OpenRouter, any OpenAI-compatible gateway, or
an HF Inference Endpoint with ``LLM_BASE_URL`` / ``LLM_API_KEY`` / ``LLM_MODEL``.
No key configured? It degrades gracefully to the offline rule backend, so the
CLI always works.

The API client is deliberately dependency-free (httpx only) and the request
shape is stable JSON, which also keeps unit tests deterministic: the tests
inject a fake client instead of hitting a network.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx

from .patches import build_patch, inline_fix_hint


@runtime_checkable
class ChatClient(Protocol):
    """Anything with ``configured`` + ``chat_json`` works as a backend."""

    @property
    def configured(self) -> bool: ...

    def chat_json(self, messages: list[dict]) -> dict: ...


PROMPT = """You are a smart-contract security reviewer. Slither found the following
issue in a Solidity contract. Explain it for a developer, in plain English:

Rule: {rule}
Impact: {impact} ({confidence} confidence)
Contract: {contract}::{function} (lines {lines})
Description: {description}

Flagged source:
```solidity
{code}
```

Answer with STRICT JSON, no markdown fences, exactly this shape:
{{"explanation": "2-4 sentences, what the bug is",
  "why_it_matters": "1-2 sentences, real-world consequence",
  "fix": "1-3 sentences, concrete remediation",
  "confidence_note": "optional string"}}
"""


class LLMClient:
    """Tiny OpenAI-compatible chat client (httpx, no SDK)."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or "").rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY") or ""
        self.model = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def chat_json(self, messages: list[dict]) -> dict:
        if not self.configured:
            raise RuntimeError("LLM backend not configured (LLM_BASE_URL + LLM_API_KEY)")
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, "temperature": 0.2},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        content = payload["choices"][0]["message"]["content"]
        return _parse_json(content)


def _parse_json(content: str) -> dict:
    """Parse model output, tolerating ```json fences and stray prose."""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in model output: {content[:200]!r}")
    return json.loads(text[start : end + 1])


class LLMExplainer:
    """Enrich findings with LLM explanations; falls back to rule backend."""

    name = "llm"

    def __init__(self, client: ChatClient | None = None):
        self.client: ChatClient = client or LLMClient()

    def enrich(self, result, source_path: str | Path) -> None:
        from .rule_backend import enrich as rule_enrich

        if not self.client.configured:
            rule_enrich(result, source_path)
            return

        for f in result.findings:
            prompt = PROMPT.format(
                rule=f.rule_id,
                impact=f.impact or "unknown",
                confidence=f.confidence or "unknown",
                contract=f.contract or "-",
                function=f.function or "-",
                lines=", ".join(str(l) for l in f.lines) or "-",
                description=f.description or "-",
                code=f.code or "(no source)",
            )
            try:
                data = self.client.chat_json(
                    [{"role": "user", "content": prompt}]
                )
                f.explanation = str(data.get("explanation") or "").strip()
                why = str(data.get("why_it_matters") or "").strip()
                f.fix = str(data.get("fix") or "").strip()
                if why:
                    f.explanation = f"{f.explanation}\n\nWhy it matters: {why}"
                f.source = "llm"
            except Exception as exc:
                f.explanation = f"(LLM call failed: {exc})\n" + f.explanation
            f.patch = build_patch(source_path, f, hint=inline_fix_hint(f) if not f.fix else f.fix)