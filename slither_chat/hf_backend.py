"""Hugging Face integration.

Two independent integrations, both usable with public (token-free) reads:

1. **Model** — zero-shot severity scoring. ``typeform/distilbert-base-uncased-mnli``
   re-classifies each finding's description into our severity scale on CPU, no
   API key, no GPU. Used by ``--backend hf``.

2. **Dataset** — benchmark corpora. ``slither-chat benchmark`` pulls real
   audited contracts from an HF dataset whose rows carry Slither ground truth
   (e.g. ``Royal-lobster/Slither-Audited-Solidity-QA``), runs the local audit
   pipeline over them, and reports per-rule precision/recall/F1.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
from huggingface_hub import HfApi, hf_hub_download

from .analyzer import run_slither
from .models import AnalysisError, Finding, Severity, severity_from_impact
from .parser import normalize

log = logging.getLogger("slither_chat.hf")

# ---------------------------------------------------------------------------
# Benchmarked corpora (public, ungated, column schema verified on the Hub).
# Each entry: (dataset id, column with Solidity source, column with ground truth)
# ---------------------------------------------------------------------------
BENCHMARK_DATASETS: dict[str, dict] = {
    "slither-audited-solidity-qa": {
        "id": "Royal-lobster/Slither-Audited-Solidity-QA",
        "source_col": "input",
        "truth_col": "output",
        "note": "1,748 test contracts; Slither audit text as ground truth",
    },
    "smart-contract-w-slither": {
        "id": "jainabh/smart-contract-w-Slither",
        "source_col": "contract_source",
        "truth_col": "Slither Detectors",
        "note": "2,000 contracts labeled malicious/benign, with Slither detector text",
    },
}


def list_benchmark_datasets() -> dict[str, dict]:
    return BENCHMARK_DATASETS


# ---------------------------------------------------------------------------
# Ground-truth parsing  ("2) reentrancy-no-eth with Medium impact" -> ("reentrancy-no-eth", Medium))
# ---------------------------------------------------------------------------
_GT_LINE = re.compile(
    r"(?im)^\s*(?:[-*]\s*|\d+[\)\.]\s*)?(?P<rule>[a-z0-9-]+)\s+with\s+(?P<sev>[a-z]+)\s+impact"
)


def parse_ground_truth(text: str) -> list[tuple[str, str]]:
    """Parse Slither audit *text* (as found in HF datasets) into (rule, impact)."""
    out: list[tuple[str, str]] = []
    for m in _GT_LINE.finditer(text or ""):
        out.append((m.group("rule").strip().lower(), m.group("sev").strip().lower()))
    return out


# ---------------------------------------------------------------------------
# Dataset table loading (cached by huggingface_hub; no auth required)
# ---------------------------------------------------------------------------
def fetch_dataset_table(
    dataset: str, split: str = "test", limit: Optional[int] = None
) -> pd.DataFrame:
    """Return rows of an HF dataset as a DataFrame (first parquet shard)."""
    info = BENCHMARK_DATASETS[dataset]
    repo_id = info["id"]
    api = HfApi()
    files = [f.rfilename for f in api.dataset_info(repo_id).siblings]
    candidates = [f for f in files if f.endswith(".parquet") and split in f]
    if not candidates:
        candidates = [f for f in files if f.endswith(".parquet")]
    if not candidates:
        raise AnalysisError(f"no parquet files found for {repo_id}")

    path = hf_hub_download(repo_id, candidates[0], repo_type="dataset")
    df = pd.read_parquet(path)
    if df is None:  # pragma: no cover - parquet always yields a frame
        raise AnalysisError(f"could not read parquet for {repo_id}")
    required = {info["source_col"], info["truth_col"]}
    missing = required - set(df.columns)
    if missing:
        raise AnalysisError(
            f"dataset {repo_id} missing expected columns {sorted(missing)}; "
            f"found {sorted(df.columns)}"
        )
    if limit is not None:
        df = df.head(limit)
    return df.dropna(subset=[info["source_col"], info["truth_col"]])


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------
@dataclass
class BenchmarkRow:
    index: int
    truth: set[str]
    found: set[str]
    tp: set[str]
    fp: set[str]
    fn: set[str]
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def _rule_id_of(f: Finding) -> str:
    return f.rule_id


def run_benchmark(
    dataset: str,
    limit: Optional[int] = None,
    backend: str = "rule",
    enrich_fn=None,  # callable(result, source_path) or None
    solc_versions: Optional[list[str]] = None,
    include_informational: bool = False,
) -> tuple[list[BenchmarkRow], dict]:
    """Audit ``limit`` contracts from the HF dataset and score vs ground truth.

    Returns (rows, summary). Network access to the Hub is required; the
    pipeline itself runs fully local. ``solc_versions`` enables
    crytic-compile's solc-select integration so contracts with old pragmas
    compile (see :func:`slither_chat.analyzer.run_slither`).

    By default only impact-bearing findings (High/Medium/Low) contribute to
    the score — informational noise (naming styles etc.) is excluded, which
    matches how the corpus authors wrote the ground truth. Pass
    ``include_informational=True`` to score every detector.
    """
    df = fetch_dataset_table(dataset, limit=limit)
    info = BENCHMARK_DATASETS[dataset]
    rows: list[BenchmarkRow] = []
    found_rules: set[str] = set()
    truth_rules: set[str] = set()
    global_tp = global_fp = global_fn = 0

    def significant(f: Finding) -> bool:
        return include_informational or f.severity is not Severity.INFORMATIONAL

    for idx, row in df.iterrows():
        source = str(row[info["source_col"]])
        truth = set(r for r, _ in parse_ground_truth(str(row[info["truth_col"]])))
        truth_rules |= truth

        br = BenchmarkRow(index=idx, truth=truth, found=set(), tp=set(), fp=set(), fn=set())
        with tempfile.TemporaryDirectory(prefix="slither-chat-bench-") as td:
            sol_path = Path(td) / "contract.sol"
            try:
                sol_path.write_text(source, encoding="utf-8")
                payload = run_slither(sol_path, timeout=180, solc_versions=solc_versions)
                result = normalize(payload, sol_path)
                if enrich_fn is not None:
                    enrich_fn(result, sol_path)
                found = {_rule_id_of(f) for f in result.findings if significant(f)}
            except Exception as exc:  # noqa: BLE001 - per-row isolation
                br.error = f"{type(exc).__name__}: {exc}"[:300]
                rows.append(br)
                continue

        br.found = found
        found_rules |= found
        br.tp = found & truth
        br.fp = found - truth
        br.fn = truth - found
        global_tp += len(br.tp)
        global_fp += len(br.fp)
        global_fn += len(br.fn)
        rows.append(br)

    summary = _summarize(rows, global_tp, global_fp, global_fn, found_rules, truth_rules)
    return rows, summary


def _summarize(rows, tp, fp, fn, found_rules, truth_rules) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "contracts": len(rows),
        "analyzed": sum(1 for r in rows if r.ok),
        "errors": sum(1 for r in rows if not r.ok),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "rules_detected": len(found_rules),
        "rules_present": len(truth_rules),
    }


# ---------------------------------------------------------------------------
# Zero-shot vulnerability-class tagger (CPU, transformers)
#
# A small on-device NLI model tags every finding with the vulnerability class
# it best matches (reentrancy, access control, oracle manipulation, ...) and a
# confidence score. It is a *second opinion* for triage, not the source of
# truth: severity still comes from Slither's impact.
# ---------------------------------------------------------------------------
# Two verified models:
#   strong (default): MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli (~430 MB)
#   light:            typeform/distilbert-base-uncased-mnli       (~270 MB)
_MODEL_ID = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
_LIGHT_MODEL_ID = "typeform/distilbert-base-uncased-mnli"

_CLASSES = [
    "reentrancy attack where a contract is called again before state updates",
    "access control problem where untrusted callers reach privileged functions",
    "price oracle manipulation where an attacker skews asset prices or quotes",
    "arithmetic precision loss in division or multiplication",
    "unchecked external call whose failure is silently ignored",
    "predictable randomness derived from block data",
    "code style or gas optimization note",
]

# short display name for each class (same order as _CLASSES)
_CLASS_NAMES = [
    "reentrancy",
    "access control",
    "oracle manipulation",
    "arithmetic precision",
    "unchecked call",
    "predictable randomness",
    "style/gas",
]


class ZeroShotVulnClassifier:
    """Tag findings with vulnerability classes using a local NLI model.

    Lazily loads the model (cached by huggingface_hub after the first
    download); classification itself never touches the network.
    """

    def __init__(self, model_id: str = _MODEL_ID, classes: list[str] | None = None):
        self.model_id = model_id
        self.classes = list(classes or _CLASSES)
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            from transformers import pipeline  # optional dependency

            self._pipeline = pipeline(
                "zero-shot-classification",
                model=self.model_id,
                device=-1,  # CPU
            )
        return self._pipeline

    def classify(self, text: str) -> tuple[str, float]:
        """Return (class_name, confidence) for one finding description."""
        pipe = self._load()
        out = pipe([text], self.classes)[0]
        labels, scores = out["labels"], out["scores"]
        best = max(range(len(labels)), key=lambda i: scores[i])
        if labels[best] in self.classes:
            idx = self.classes.index(labels[best])
            short = _CLASS_NAMES[idx]
        else:  # pragma: no cover - model returned an unexpected label
            short = "unknown"
        return short, round(scores[best], 3)

    def enrich(self, result, source_path: str | Path) -> None:
        for f in result.findings:
            text = (
                f"{f.rule_id}: {f.description}".replace("\n", " ")
                + f" Contract {f.contract} function {f.function}"
            )
            try:
                f.issue_class, f.class_confidence = self.classify(text)
                f.source = "hf"
            except Exception as exc:  # noqa: BLE001 - keep pipeline alive
                log.warning("zero-shot classify failed for %s: %s", f.rule_id, exc)


def json_default(o):
    if isinstance(o, Severity):
        return o.value
    raise TypeError(f"not serializable: {type(o)}")