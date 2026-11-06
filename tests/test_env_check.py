"""Tests for the environment check (`tminus env`)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from tminus.cli.main import app as cli
from tminus.engine.env_check import (
    check_environment,
    detect,
    format_rows,
    judge,
    needs_text,
)
from tminus.engine.loader import load_target
from tminus.engine.models import RequirementSpec

SPEC = RequirementSpec(minimum="3.14", below="3.15")


def _runner(outputs: dict[str, str]) -> "callable":  # type: ignore[valid-type]
    """A fake command runner: returns the canned output for the command's first word."""

    def run(args: list[str]) -> str | None:
        """Look up the output for the command being run."""
        return outputs.get(args[0])

    return run


FULL = {
    "python3": "Python 3.14.1",
    "node": "v24.2.0",
    "mariadb": "mariadb from 11.8.2-MariaDB, client 15.2 for linux-gnu (x86_64)",
    "redis-server": "Redis server v=7.0.15 sha=00000000:0 malloc=jemalloc-5.3.0 bits=64",
}


def test_needs_text() -> None:
    """Requirements read naturally."""
    assert needs_text(SPEC) == ">=3.14,<3.15"
    assert (
        needs_text(RequirementSpec(minimum="10.6", recommended="11.8"))
        == ">=10.6 (11.8 recommended)"
    )


@pytest.mark.parametrize(
    ("found", "status"),
    [("3.14.1", "ok"), ("3.12.3", "upgrade"), ("3.15.0", "upgrade"), (None, "missing")],
)
def test_judge_python(found: str | None, status: str) -> None:
    """Too old, too new and missing are all reported; the right version is ok."""
    assert judge(found, SPEC)[0] == status


def test_judge_recommended_version() -> None:
    """A version that meets the minimum but not the recommendation is ok with a note."""
    status, note = judge("10.11.6", RequirementSpec(minimum="10.6", recommended="11.8"))
    assert status == "ok"
    assert "11.8 is recommended" in note


def test_detect_all_tools_with_a_fake_runner() -> None:
    """Version numbers are read from each tool's output."""
    run = _runner(FULL)
    assert detect("python", run, None)[0] == "3.14.1"
    assert detect("node", run, None)[0] == "24.2.0"
    assert detect("mariadb", run, None)[0] == "11.8.2"
    assert detect("redis", run, None)[0] == "7.0.15"


def test_detect_old_mysql_style_output() -> None:
    """The `Distrib 10.11.6-MariaDB` style of older clients is understood."""
    out = {"mysql": "mysql  Ver 15.1 Distrib 10.11.6-MariaDB, for debian-linux-gnu (x86_64)"}
    assert detect("mariadb", _runner(out), None)[0] == "10.11.6"


def test_detect_missing_tool() -> None:
    """A tool that is not installed has no version."""
    assert detect("redis", _runner({}), None) == (None, "")


def test_bench_python_is_read_from_pyvenv_cfg(tmp_path: Path) -> None:
    """The bench's own interpreter version comes from env/pyvenv.cfg, without running it."""
    (tmp_path / "env").mkdir()
    (tmp_path / "env" / "pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.11.9\n")
    version, where = detect("python", _runner(FULL), tmp_path)
    assert version == "3.11.9"
    assert where.endswith("pyvenv.cfg")


def test_check_environment_for_v16() -> None:
    """With everything installed at v16 versions the report is all ok."""
    rows = check_environment(load_target("v16").requirements, _runner(FULL), None)
    assert [r.status for r in rows] == ["ok", "ok", "ok", "ok"]


def test_format_rows_mentions_a_new_bench() -> None:
    """The report ends with the new-bench reminder and shows UPGRADE NEEDED."""
    old = dict(FULL, python3="Python 3.12.3")
    rows = check_environment(load_target("v16").requirements, _runner(old), None)
    text = format_rows(rows, "v16")
    assert "UPGRADE NEEDED" in text
    assert "NEW bench" in text


def test_cli_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`tminus env` prints the table and exits 0 (it is informational)."""
    monkeypatch.setattr("tminus.cli.main.run_command", _runner(FULL))
    result = CliRunner().invoke(cli, ["env", str(tmp_path), "--target", "v16"])
    assert result.exit_code == 0
    assert "python" in result.output
    assert "UPGRADE NEEDED" not in result.output


def test_cli_env_unknown_target(tmp_path: Path) -> None:
    """An unknown target is a usage error."""
    assert CliRunner().invoke(cli, ["env", str(tmp_path), "--target", "v99"]).exit_code == 2
