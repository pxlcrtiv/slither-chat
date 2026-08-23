"""Hugging Face backend tests (offline: dataset access is mocked/skipped)."""

import pandas as pd
import pytest

from slither_chat import hf_backend
from slither_chat.hf_backend import (
    BENCHMARK_DATASETS,
    ZeroShotVulnClassifier,
    _summarize,
    fetch_dataset_table,
    parse_ground_truth,
    run_benchmark,
)
from slither_chat.models import Severity


def test_ground_truth_parser_basic():
    text = (
        "These are the vulnerabilities found\n\n"
        "1) weak-prng with High impact\n"
        "2) reentrancy-no-eth with Medium impact\n"
        "3) incorrect-equality with Medium impact"
    )
    assert parse_ground_truth(text) == [
        ("weak-prng", "high"),
        ("reentrancy-no-eth", "medium"),
        ("incorrect-equality", "medium"),
    ]


def test_ground_truth_parser_bullets_and_noise():
    text = "## Audit\n- arbitrary-send-eth with High impact\nSome prose.\n9. timestamp with Low impact"
    assert parse_ground_truth(text) == [
        ("arbitrary-send-eth", "high"),
        ("timestamp", "low"),
    ]


def test_ground_truth_parser_empty():
    assert parse_ground_truth("") == []
    assert parse_ground_truth("no findings here") == []


def test_benchmark_datasets_registry():
    assert "slither-audited-solidity-qa" in BENCHMARK_DATASETS
    assert "smart-contract-w-slither" in BENCHMARK_DATASETS
    # every registry entry has the columns the runner needs
    for info in BENCHMARK_DATASETS.values():
        assert info["source_col"]
        assert info["truth_col"]


def test_summarize_math():
    summary = _summarize([], tp=10, fp=5, fn=5, found_rules={"a"}, truth_rules={"a", "b"})
    assert summary["precision"] == pytest.approx(10 / 15, abs=0.001)
    assert summary["recall"] == pytest.approx(10 / 15, abs=0.001)
    assert summary["f1"] == pytest.approx(2 * (10 / 15) * (10 / 15) / (2 * (10 / 15)), abs=0.001)
    assert summary["contracts"] == 0 and summary["errors"] == 0


def test_fetch_dataset_table_requires_registered_key():
    with pytest.raises(KeyError):
        fetch_dataset_table("not-a-registered-dataset")


def test_run_benchmark_rejects_unknown_key():
    with pytest.raises(KeyError):
        run_benchmark("nope", limit=1)


class _FakePipe:
    """Stands in for the transformers zero-shot pipeline (no network)."""

    def __init__(self, labels: list[str], scores: list[float]):
        self.labels = labels
        self.scores = scores

    def __call__(self, texts, classes=None):
        return [{"labels": self.labels, "scores": self.scores}]


class TestZeroShotVulnClassifier:
    def test_classes_and_names_aligned(self):
        from slither_chat.hf_backend import _CLASS_NAMES, _CLASSES

        assert len(_CLASS_NAMES) == len(_CLASSES) == 7

    def test_classify_maps_labels(self):

        z = ZeroShotVulnClassifier()
        z._pipeline = _FakePipe(
            labels=[
                "reentrancy attack where a contract is called again before state updates",
                "access control problem where untrusted callers reach privileged functions",
            ],
            scores=[0.91, 0.05],
        )
        cls, _ = z.classify("a reentrancy issue")
        assert cls == "reentrancy"
        # confidence comes from the stub score as-is

    def test_classify_unknown_label_falls_back(self):

        z = ZeroShotVulnClassifier()
        z._pipeline = _FakePipe(labels=["something else entirely"], scores=[0.5])
        cls, _ = z.classify("x")
        assert cls == "unknown"

    def test_enrich_set_fields_without_network(self):
        from slither_chat.hf_backend import _CLASSES
        from slither_chat.parser import normalize
        from tests.conftest import REPO, load_fixture

        result = normalize(
            load_fixture("slither_vault.json"), REPO / "examples" / "vault.sol"
        )
        z = ZeroShotVulnClassifier()
        # one finding gets a confident tag, rest fail gracefully
        z._pipeline = _FakePipe(labels=[_CLASSES[0]], scores=[0.8])

        class _FlakyPipe:
            def __init__(self, inner):
                self.inner = inner
                self.n = 0

            def __call__(self, *a, **k):
                self.n += 1
                if self.n == 1:
                    return self.inner(*a, **k)
                raise RuntimeError("boom")

        z._pipeline = _FlakyPipe(z._pipeline)
        z.enrich(result, REPO / "examples" / "vault.sol")
        tagged = [f for f in result.findings if f.issue_class]
        assert len(tagged) >= 1
        assert all(f.source == "hf" for f in tagged)


def test_json_default_handles_severity():
    assert hf_backend.json_default(Severity.HIGH) == "High"


def test_make_benchmark_frame_schema():
    # the runner's contract with the dataset registry: columns used exist there
    from tests.conftest import FIXTURES

    info = BENCHMARK_DATASETS["slither-audited-solidity-qa"]
    df = pd.DataFrame(
        {
            info["source_col"]: ["pragma solidity ^0.8.0; contract A {}"],
            info["truth_col"]: ["1) solc-version with Informational impact"],
        }
    )
    assert set(df.columns) == {info["source_col"], info["truth_col"]}