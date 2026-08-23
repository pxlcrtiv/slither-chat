# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-08-23

Initial public release.

### Added

- `slither-chat audit` — Slither subprocess wrapper (JSON mode) with
  normalized Finding model: rule id, severity, confidence, contract/function,
  exact lines, source snippet.
- Offline knowledge-base explainer (`--backend rule`, default) covering
  ~25 detector families, with `what / why / fix` structure.
- Hugging Face zero-shot vulnerability-class tagging (`--backend hf`,
  `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`, CPU, token-free, with
  confidence scores).
- OpenAI-compatible LLM explainer (`--backend llm`, httpx-only, env-based
  config, graceful degradation to the rule backend).
- Line-precise patch hints as unified diffs (`patches.py`).
- Markdown, rich terminal, and SVG report renderers; full JSON export.
- `slither-chat benchmark` — precision/recall/F1 scoring against real audited
  contracts from `Royal-lobster/Slither-Audited-Solidity-QA` (and
  `jainabh/smart-contract-w-Slither`), no HF token required.
- `slither-chat datasets` — registry of supported benchmark corpora.
- Three deliberately vulnerable example contracts with integration tests
  (reentrancy vault, tx.origin gateway, naive oracle).
- GitHub Actions CI: unit tests (py3.11/3.12, offline), integration tests,
  ruff lint, benchmark smoke test.
- `scripts/make_fixture.py` to regenerate the captured slither JSON fixture.