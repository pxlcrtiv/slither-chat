"""LLM backend tests with an injected fake client (no network)."""

import httpx
import pytest

from slither_chat.llm_backend import LLMClient, LLMExplainer, _parse_json
from slither_chat.rule_backend import KB


class FakeClient:
    """Deterministic stand-in for an OpenAI-compatible endpoint."""

    def __init__(self, payload: dict, fail: bool = False):
        self.payload = payload
        self.fail = fail
        self.calls: list[dict] = []

    @property
    def configured(self) -> bool:
        return True

    def chat_json(self, messages: list[dict]) -> dict:
        self.calls.append(messages)
        if self.fail:
            raise httpx.ConnectError("simulated network failure")
        return self.payload


def test_parse_json_fenced():
    raw = '```json\n{"explanation": "hi", "fix": "bye"}\n```'
    assert _parse_json(raw) == {"explanation": "hi", "fix": "bye"}


def test_parse_json_stray_prose():
    raw = 'Sure! Here you go: {"explanation": "a", "why_it_matters": "b", "fix": "c"} Hope that helps!'
    parsed = _parse_json(raw)
    assert parsed["explanation"] == "a"


def test_parse_json_bad():
    with pytest.raises(ValueError):
        _parse_json("no json at all")


def test_llm_explainer_enriches():
    from slither_chat.parser import normalize
    from tests.conftest import REPO, load_fixture

    src = REPO / "examples" / "vault.sol"
    result = normalize(load_fixture("slither_vault.json"), src)
    payload = {
        "explanation": "The call is made before state is updated.",
        "why_it_matters": "An attacker re-enters and drains funds.",
        "fix": "Apply checks-effects-interactions.",
        "confidence_note": "",
    }
    client = FakeClient(payload)
    LLMExplainer(client=client).enrich(result, src)
    assert client.calls, "the client must be called for every finding"
    for f in result.findings:
        assert f.explanation
        assert f.fix
        assert f.source == "llm"
        assert f.patch
    first_msgs = client.calls[0][0]["content"]
    assert "reentrancy-eth" in first_msgs or "slither" in first_msgs.lower()


def test_llm_failure_degrades_gracefully():
    from slither_chat.parser import normalize
    from tests.conftest import REPO, load_fixture

    src = REPO / "examples" / "vault.sol"
    result = normalize(load_fixture("slither_vault.json"), src)
    LLMExplainer(client=FakeClient({}, fail=True)).enrich(result, src)
    # pipeline survives: every finding still has some explanation/patch
    assert all(f.explanation for f in result.findings)
    assert all(f.patch for f in result.findings)


def test_unconfigured_client_raises():
    client = LLMClient(base_url="", api_key="")
    assert not client.configured
    with pytest.raises(RuntimeError):
        client.chat_json([{"role": "user", "content": "hi"}])


def test_unconfigured_explainer_falls_back_to_rules():
    from slither_chat.parser import normalize
    from tests.conftest import REPO, load_fixture

    src = REPO / "examples" / "vault.sol"
    result = normalize(load_fixture("slither_vault.json"), src)
    LLMExplainer(client=LLMClient(base_url="", api_key="")).enrich(result, src)
    reent = next(f for f in result.findings if f.rule_id == "reentrancy-eth")
    assert reent.source == "rule"
    assert "checks-effects-interactions" in reent.fix.lower() or \
           "checks-effects-interactions" in reent.explanation.lower()
    assert reent.rule_id in KB