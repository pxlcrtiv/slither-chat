"""Regenerate tests/fixtures/slither_vault.json from a live run (dev tool)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slither_chat.analyzer import run_slither  # noqa: E402

payload = run_slither("examples/vault.sol")
stripped = {
    "results": payload["results"],
    "_meta": payload.get("_meta", {}),
}
out = "tests/fixtures/slither_vault.json"
with open(out, "w") as f:
    json.dump(stripped, f, indent=1)
print(f"wrote {out}: {len(stripped['results']['detectors'])} detector records")