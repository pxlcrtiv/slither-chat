"""Normalize Slither's JSON output into :class:`Finding` objects."""

from __future__ import annotations

from pathlib import Path

from .models import AuditResult, Finding, severity_from_impact

_SNIPPET_PAD = 3          # context lines around a flagged region
_SNIPPET_MAX_LINES = 45   # cap for the extracted snippet


def _element_contract(el: dict) -> str:
    """Contract name lives in type_specific_fields.parent for most detectors."""
    tsf = el.get("type_specific_fields") or {}
    parent = tsf.get("parent") or {}
    if isinstance(parent, dict) and parent.get("type") == "contract":
        return str(parent.get("name") or "")
    # fallback: slither-compilation source unit info
    meta = el.get("additional_fields") or {}
    if isinstance(meta, dict) and meta.get("contract"):
        return str(meta["contract"])
    return ""


def _first_contract(elements: list[dict]) -> str:
    for el in elements:
        name = _element_contract(el)
        if name:
            return name
    return ""


def _first_function(elements: list[dict]) -> str:
    for el in elements:
        if el.get("type") == "function":
            return str(el.get("name") or "")
    return ""


def _extract_lines(elements: list[dict]) -> list[int]:
    lines: set[int] = set()
    for el in elements:
        sm = el.get("source_mapping") or {}
        mapped = sm.get("lines") if isinstance(sm.get("lines"), list) else None
        if mapped:
            lines.update(int(l) for l in mapped if isinstance(l, (int, float)))
            continue
        start = sm.get("start")
        length = int(sm.get("length") or 0)
        if isinstance(start, (int, float)) and length > 0:
            lines.update(range(int(start), int(start) + length))
    return sorted(l for l in lines if l > 0)


def _extract_snippet(source_path: Path, lines: list[int]) -> str:
    """Pull the flagged source lines plus a little context."""
    if not lines:
        return ""
    try:
        text = source_path.read_text(errors="replace").splitlines()
    except OSError:
        return ""
    lo = max(1, min(lines) - _SNIPPET_PAD)
    hi = min(len(text), max(lines) + _SNIPPET_PAD)
    out = []
    for i in range(lo, hi + 1):
        mark = ">>" if i in lines else "  "
        out.append(f"{mark} {i:4d} | {text[i - 1]}")
    if len(out) > _SNIPPET_MAX_LINES:
        out = out[: _SNIPPET_MAX_LINES] + ["  ... (truncated)"]
    return "\n".join(out)


def normalize(payload: dict, source_path: str | Path) -> AuditResult:
    """Map a raw slither ``--json`` payload onto :class:`AuditResult`."""
    path = Path(source_path)
    results = payload.get("results", {})
    records: list[dict] = results.get("detectors", [])
    warnings = list(results.get("warnings", []))

    seen: set[tuple] = set()
    findings: list[Finding] = []
    for rec in records:
        elements = rec.get("elements", []) or []
        lines = _extract_lines(elements)
        f = Finding(
            rule_id=rec.get("check", "") or "unknown-rule",
            description=(rec.get("description") or "").strip(),
            impact=rec.get("impact", "") or "",
            confidence=rec.get("confidence", "") or "",
            severity=severity_from_impact(rec.get("impact", "")),
            contract=_first_contract(elements),
            function=_first_function(elements),
            lines=lines,
            code=_extract_snippet(path, lines),
            evidence=_shorten(rec.get("markdown") or "", 600),
        )
        key = f.key
        if key in seen:  # slither often repeats a detector per element
            continue
        seen.add(key)
        findings.append(f)

    result = AuditResult(
        source_path=str(path),
        findings=findings,
        warnings=warnings,
        slither_version=str((payload.get("_meta") or {}).get("slither_version", "")),
        compiler=str((payload.get("_meta") or {}).get("compiler", "")),
        duration_sec=float((payload.get("_meta") or {}).get("duration_sec", 0.0)),
    )
    return result


def _shorten(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"