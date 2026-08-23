"""CLI tests via click's CliRunner (audit uses the real slither binary)."""

import json

import pytest
from click.testing import CliRunner

from slither_chat.cli import cli
from tests.conftest import REPO, requires_solc


@pytest.fixture(scope="module")
def runner():
    return CliRunner()


def test_version(runner):
    res = runner.invoke(cli, ["--version"])
    assert res.exit_code == 0
    assert "slither-chat" in res.output


def test_datasets_lists_corpora(runner):
    res = runner.invoke(cli, ["datasets"])
    assert res.exit_code == 0
    assert "Royal-lobster" in res.output
    assert "slither-audited-solidity-qa" in res.output


def test_audit_rule_backend_plain(runner):
    requires_solc()
    res = runner.invoke(
        cli, ["audit", str(REPO / "examples" / "vault.sol"), "--backend", "rule", "--plain"]
    )
    assert res.exit_code == 0, res.output
    assert "reentrancy-eth" in res.output
    assert "[High]" in res.output
    assert "checks-effects-interactions" in res.output


def test_audit_markdown_and_json_outputs(runner, tmp_path):
    requires_solc()
    src = REPO / "examples" / "oracle.sol"
    md = tmp_path / "report.md"
    js = tmp_path / "report.json"
    res = runner.invoke(
        cli,
        [
            "audit", str(src), "--backend", "rule", "--plain",
            "--markdown", str(md), "--json-out", str(js),
        ],
    )
    assert res.exit_code == 0, res.output
    assert md.exists() and "divide-before-multiply" in md.read_text()
    data = json.loads(js.read_text())
    assert data["backend"] == "rule"
    assert any(f["rule"] == "divide-before-multiply" for f in data["findings"])


def test_audit_missing_path(runner):
    res = runner.invoke(cli, ["audit", "/no/such/file.sol"])
    assert res.exit_code != 0


def test_audit_bad_backend(runner):
    res = runner.invoke(cli, ["audit", "x.sol", "--backend", "nope"])
    assert res.exit_code != 0
    assert "Invalid value" in res.output


def test_audit_svg_export(runner, tmp_path):
    requires_solc()
    src = REPO / "examples" / "gateway.sol"
    svg = tmp_path / "usage.svg"
    res = runner.invoke(
        cli, ["audit", str(src), "--backend", "rule", "--svg", str(svg), "--plain"]
    )
    assert res.exit_code == 0, res.output
    assert svg.exists()
    assert "<svg" in svg.read_text()