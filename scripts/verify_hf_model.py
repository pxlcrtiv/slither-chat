"""Live verification of the HF zero-shot class-tagger (downloads model once)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slither_chat.hf_backend import ZeroShotVulnClassifier  # noqa: E402

t0 = time.monotonic()
z = ZeroShotVulnClassifier()
samples = [
    "Reentrancy in ReentrantVault.withdraw: external call before state update; attacker can re-enter and drain funds.",
    "tx.origin used for authorization; phishing contracts can impersonate the owner.",
    "Division is performed before multiplication; precision loss in token math.",
    "blockhash and timestamp used to generate randomness.",
    "State variable can be declared constant.",
]
for s in samples:
    cls, conf = z.classify(s)
    print(f"{cls:20s} {conf:.2f}  <- {s[:64]}")
print(f"(model load + {len(samples)} classifications: {time.monotonic()-t0:.1f}s)")