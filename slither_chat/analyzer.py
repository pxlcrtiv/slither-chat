"""Thin wrapper around the `slither` CLI.

Runs Slither in a subprocess with ``--json`` output and returns the parsed
dict. Keeping it a subprocess boundary means slither-chat never has to fight
Slither's import-time side effects and stays robust to Slither version churn.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .models import AnalysisError

_DEFAULT_TIMEOUT_S = 240
_DEFAULT_FLAGS = [
    "--exclude-dependencies",  # skip imported deps (OpenZeppelin etc.)
    "--filter-paths", "node_modules,lib/,@openzeppelin",
    "--solc-args", "",
]


def slither_bin() -> str:
    """Resolve the slither executable (respects the SLITHER env override)."""
    return os.environ.get("SLITHER_BIN") or shutil.which("slither") or "slither"


def slither_version() -> str:
    try:
        proc = subprocess.run(
            [slither_bin(), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = (proc.stdout or proc.stderr).strip().splitlines()
        return out[-1] if out else "unknown"
    except Exception:  # pragma: no cover - environment dependent
        return "unknown"


def run_slither(
    source: str | Path,
    timeout: int = _DEFAULT_TIMEOUT_S,
    extra_flags: list[str] | None = None,
    solc_versions: list[str] | None = None,
) -> dict:
    """Run Slither on ``source`` and return the parsed ``--json`` output.

    Raises :class:`AnalysisError` when slither is missing, times out, or
    produces no analyzable output.

    ``solc_versions`` (or the ``SLITHER_CHAT_SOLC_VERSIONS`` env var, comma
    separated) enables crytic-compile's solc-select integration: each contract
    is compiled with the best installed version for its pragma instead of the
    ``solc`` found on PATH. Useful for corpora spanning 0.4.x-0.8.x.
    """
    source = Path(source)
    if not source.exists():
        raise AnalysisError(f"path does not exist: {source}")

    versions = list(solc_versions or [])
    if not versions and os.environ.get("SLITHER_CHAT_SOLC_VERSIONS"):
        versions = [
            v.strip()
            for v in os.environ["SLITHER_CHAT_SOLC_VERSIONS"].split(",")
            if v.strip()
        ]

    flags = list(_DEFAULT_FLAGS) + (extra_flags or [])
    if versions:
        flags += ["--solc-solcs-select", ",".join(versions)]
    with tempfile.TemporaryDirectory(prefix="slither-chat-") as td:
        out_file = Path(td) / "slither.json"
        cmd = [slither_bin(), str(source), "--json", str(out_file), *flags]
        started = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            raise AnalysisError(
                f"slither timed out after {timeout}s (source may be too large)"
            )

        if not out_file.exists():
            tail = (proc.stderr or proc.stdout or "").strip()[-1500:]
            raise AnalysisError(
                f"slither produced no JSON output (exit={proc.returncode}):\n{tail}"
            )

        try:
            payload = json.loads(out_file.read_text())
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise AnalysisError(f"slither emitted invalid JSON: {exc}")

        payload["_meta"] = {
            "duration_sec": round(time.monotonic() - started, 2),
            "exit_code": proc.returncode,
            "slither_version": slither_version(),
            "compiler": (proc.stderr or "")
            .splitlines()[0]
            .strip()
            if proc.stderr
            else "",
        }
        return payload