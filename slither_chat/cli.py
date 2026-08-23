"""Command-line interface (click)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import __version__, hf_backend
from .models import AnalysisError, SEVERITY_ORDER
from .report import build_rich_console, render_markdown, render_rich, render_svg

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
DATASET_KEYS = list(hf_backend.BENCHMARK_DATASETS.keys())


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, prog_name="slither-chat")
def cli() -> None:
    """slither-chat — smart-contract audit copilot (Slither + explainers)."""


@cli.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--backend",
    type=click.Choice(["rule", "hf", "llm"], case_sensitive=False),
    default="rule",
    show_default=True,
    help="Explainer backend: rule (offline KB), hf (zero-shot HF model), llm (API).",
)
@click.option("--hf-model", default=None, help="HF zero-shot model id (backend=hf).")
@click.option(
    "--markdown",
    "markdown_out",
    type=click.Path(path_type=Path),
    default=None,
    help="Also write a markdown report to this path.",
)
@click.option(
    "--svg",
    "svg_out",
    type=click.Path(path_type=Path),
    default=None,
    help="Export a terminal-style SVG of the report (for READMEs).",
)
@click.option("--json-out", type=click.Path(path_type=Path), default=None,
              help="Dump the full audit as JSON.")
@click.option("--plain/--rich", "plain", default=False,
              help="Plain text output instead of rich formatting.")
def audit(
    source: Path,
    backend: str,
    hf_model: str | None,
    markdown_out: Path | None,
    svg_out: Path | None,
    json_out: Path | None,
    plain: bool,
) -> None:
    """Audit a Solidity file (or directory) and explain every finding."""
    from .pipeline import audit as run_audit

    try:
        result = run_audit(source, backend=backend, hf_model=hf_model)
    except AnalysisError as exc:
        raise click.ClickException(str(exc))

    if markdown_out:
        markdown_out.write_text(render_markdown(result), encoding="utf-8")
        click.echo(f"markdown report: {markdown_out}")
    if svg_out:
        render_svg(result, svg_out)
        click.echo(f"svg report: {svg_out}")
    if json_out:
        json_out.write_text(_audit_json(result), encoding="utf-8")
        click.echo(f"json report: {json_out}")

    if plain:
        click.echo(_plain_report(result))
    else:
        render_rich(result, build_rich_console())


@cli.command("benchmark")
@click.option(
    "--dataset",
    type=click.Choice(DATASET_KEYS, case_sensitive=False),
    default="slither-audited-solidity-qa",
    show_default=True,
    help="HF dataset to benchmark against (ground truth = real Slither audits).",
)
@click.option("--limit", type=click.IntRange(1, 500), default=20, show_default=True,
              help="Number of contracts to audit (hosted corpus row count).")
@click.option("--backend", type=click.Choice(["rule", "hf", "llm"], case_sensitive=False),
              default="rule", show_default=True)
@click.option("--bench-all", is_flag=True, default=False,
              help="Include informational findings in the score (default: "
                   "impact-bearing High/Medium/Low only).")
@click.option("--json-out", type=click.Path(path_type=Path), default=None)
def benchmark(dataset: str, limit: int, backend: str, bench_all: bool,
              json_out: Path | None) -> None:
    """Score the local audit pipeline against real audited contracts from HF.

    Example:  slither-chat benchmark --limit 25
    Pulls contracts from the Hugging Face dataset, runs the full local pipeline
    (Slither + explainer), and reports per-run precision/recall/F1 versus the
    Slither ground truth recorded in the dataset.
    """
    from .pipeline import audit as run_audit

    info = hf_backend.BENCHMARK_DATASETS[dataset]
    click.echo(
        f"benchmark corpus: {info['id']} [{info['note']}] (backend={backend}, "
        f"limit={limit})"
    )

    solc_versions = _detect_solc_versions()
    if solc_versions:
        click.echo(f"solc versions (solc-select): {', '.join(solc_versions)}")

    def enrich_for_bench(result, source_path):
        # Reuse the pipeline so the benchmark scores exactly what `audit` ships.
        if backend == "rule":
            from .rule_backend import enrich
            enrich(result, source_path)
        elif backend == "hf":
            from .hf_enrich import enrich_with_hf
            enrich_with_hf(result, source_path)
        else:
            from .llm_backend import LLMExplainer
            LLMExplainer().enrich(result, source_path)

    rows, summary = hf_backend.run_benchmark(
        dataset,
        limit=limit,
        backend=backend,
        enrich_fn=enrich_for_bench,
        solc_versions=solc_versions,
        include_informational=bench_all,
    )
    if json_out:
        json_out.write_text(
            json.dumps(
                {
                    "dataset": info["id"],
                    "backend": backend,
                    "summary": summary,
                    "rows": [
                        {
                            "index": r.index,
                            "truth": sorted(r.truth),
                            "found": sorted(r.found),
                            "tp": sorted(r.tp),
                            "fp": sorted(r.fp),
                            "fn": sorted(r.fn),
                            "error": r.error,
                        }
                        for r in rows
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        click.echo(f"json: {json_out}")

    console = build_rich_console(width=140)
    from rich.table import Table

    t = Table(title=f"Benchmark vs {info['id']}", header_style="bold")
    for col in ("Metric", "Value"):
        t.add_column(col)
    t.add_row("Contracts (rows)", str(summary["contracts"]))
    t.add_row("Analyzed / errors",
              f"{summary['analyzed']} / {summary['errors']}")
    t.add_row("True positives", str(summary["true_positives"]))
    t.add_row("False positives", str(summary["false_positives"]))
    t.add_row("False negatives", str(summary["false_negatives"]))
    t.add_row("Precision", f"{summary['precision']:.3f}")
    t.add_row("Recall", f"{summary['recall']:.3f}")
    t.add_row("F1", f"{summary['f1']:.3f}")
    t.add_row("Rules detected / present",
              f"{summary['rules_detected']} / {summary['rules_present']}")
    console.print(t)
    console.print(
        "Note: ground truth is Slither's own detectors; precision/recall here "
        "measure pipeline agreement, not absolute exploit risk."
    )


@cli.command("datasets")
def datasets() -> None:
    """List the Hugging Face benchmark corpora supported by `benchmark`."""
    from . import hf_backend
    from rich.table import Table

    console = build_rich_console(width=140)
    t = Table(title="Hugging Face benchmark datasets", header_style="bold")
    for col in ("Key", "Dataset", "Columns", "Note"):
        t.add_column(col)
    for key, info in hf_backend.BENCHMARK_DATASETS.items():
        t.add_row(
            key,
            info["id"],
            f"{info['source_col']} / {info['truth_col']}",
            info["note"],
        )
    console.print(t)
    console.print("All corpora are public — no Hugging Face token required.")


def _detect_solc_versions() -> list[str]:
    """Best-effort list of installed solc versions (solc-select on PATH).

    Returns [] when solc-select is unavailable; the benchmark still runs,
    and contracts with other pragmas are recorded as per-row errors.
    """
    import shutil
    import subprocess

    bin_path = shutil.which("solc-select")
    if not bin_path:
        return []
    try:
        proc = subprocess.run(
            [bin_path, "versions"], capture_output=True, text=True, timeout=30
        )
    except Exception:  # noqa: BLE001
        return []
    versions = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line and line[0].isdigit() and " " not in line.split()[0].lstrip("*"):
            versions.append(line.split()[0].lstrip("*").strip())
    return sorted({v for v in versions if v.count(".") == 2})


def _plain_report(result) -> str:
    counts = result.by_severity()
    lines = [
        f"# {result.source_path}",
        f"slither {result.slither_version} · backend={result.backend} · "
        f"{len(result.findings)} findings "
        f"(H:{counts['High']} M:{counts['Medium']} L:{counts['Low']} I:{counts['Informational']})",
        "",
    ]
    for i, f in enumerate(result.sorted(), 1):
        tag = f" [{f.issue_class} {f.class_confidence:.2f}]" if f.issue_class else ""
        lines.append(f"{i}. [{f.severity.value}] {f.rule_id} @ {f.location} lines {f.lines}{tag}")
        if f.description:
            lines.append(f"   {f.description}")
        if f.explanation:
            lines.append(f"   {f.explanation}")
        if f.fix:
            lines.append(f"   fix: {f.fix}")
        lines.append("")
    return "\n".join(lines)


def _audit_json(result) -> str:
    payload = {
        "source": result.source_path,
        "backend": result.backend,
        "slither_version": result.slither_version,
        "duration_sec": result.duration_sec,
        "findings": [
            {
                "rule": f.rule_id,
                "severity": f.severity.value,
                "impact": f.impact,
                "confidence": f.confidence,
                "contract": f.contract,
                "function": f.function,
                "lines": f.lines,
                "description": f.description,
                "explanation": f.explanation,
                "fix": f.fix,
                "patch": f.patch,
                "issue_class": f.issue_class,
                "class_confidence": f.class_confidence,
                "source": f.source,
            }
            for f in result.sorted()
        ],
    }
    return json.dumps(payload, indent=2)


def main() -> None:
    cli(prog_name="slither-chat")


if __name__ == "__main__":
    main()