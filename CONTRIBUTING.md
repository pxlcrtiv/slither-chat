# Contributing to slither-chat

First off: **thank you** — this project lives on community findings. Security
is a team sport.

## Ground rules

- Explanations live in the **knowledge base** (`rule_backend.KB`) and
  **hints** (`patches.inline_fix_hint`). Prefer improving those over adding
  one-off code paths — every KB entry upgrades *all* users.
- Patches are **suggestions**, never applied automatically. Keep that contract.
- Never hardcode a key. Everything network-y reads env vars or the Hub's
  public (token-free) endpoints by default.
- Keep the offline path working: `--backend rule` must run with no network,
  no model, no keys. New backends must degrade to it.

## Getting started

```bash
git clone https://github.com/pxlcrtiv/slither-chat
cd slither-chat
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
# optional, for --backend hf:
pip install transformers torch
# solc for the integration tests:
pip install solc-select && solc-select install 0.8.26 && solc-select use 0.8.26
```

## How to add a detector family to the KB

1. Find the detector id from slither: `slither --list-detectors | grep <name>`
2. Add a `rule_id: (what, why, fix)` entry to `rule_backend.KB`.
3. Add a one-line hint to `patches.inline_fix_hint`.
4. Add a unit test in `tests/test_rule_backend.py` asserting the explanation
   mentions the key remediation keyword.

## Tests

```bash
python -m pytest tests/ -q                 # everything (needs solc for integration)
python -m pytest tests/ -m "not slow"      # fast offline suite
python scripts/make_fixture.py             # refresh the captured slither JSON fixture
```

CI runs `pytest` (two Python versions), `ruff`, and a live benchmark smoke
test on every push/PR. If you touched the benchmark, add
`--json-out docs/benchmark.json` run output to the PR description.

## Formatting

```bash
pip install ruff && ruff check slither_chat tests scripts
```

## Daily-commit workflow (how this repo stays green)

The repo is designed for small, shippable deltas so the GitHub history bar
stays green — recruiters *do* check. Pick one of:

- **Add a KB entry** (+ test) — ~20 minutes
- **Add an example contract** to `examples/` (+ test in `test_audit_examples.py`)
- **Extend the benchmark**: register a new HF corpus in `hf_backend.BENCHMARK_DATASETS`
- **Docs**: improve a section of the README, add a troubleshooting note
- **CI**: harden the workflow, add a Python version to the matrix

Rule: **one commit per day, never an empty commit.** If a feature is half
done, commit the tested half and continue tomorrow.

## PR process

1. Branch off `main`: `git checkout -b feat/my-thing`
2. Small commits with honest messages (`feat:`, `fix:`, `docs:`, `test:`)
3. Open the PR — CI runs automatically; fix anything it flags
4. Reference which detector/rule your change addresses

## Reporting a vulnerability

Open an issue with the pattern: the contract snippet, the detector id, and
why the current KB explanation is wrong or missing. If it's a bug in the
pipeline itself (wrong severity, wrong lines), include the slither JSON.