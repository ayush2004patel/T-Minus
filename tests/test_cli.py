"""CLI tests: exit codes and output formats."""

import json
from pathlib import Path

from typer.testing import CliRunner

from tminus.cli.main import app

runner = CliRunner()


def _project(tmp_path: Path, code: str) -> Path:
    """Create a one-file app folder for a CLI run."""
    (tmp_path / "mod.py").write_text(code)
    return tmp_path


def test_version() -> None:
    """--version prints and exits 0."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "tminus" in result.output


def test_clean_project_exits_0(tmp_path: Path) -> None:
    """No findings means exit code 0."""
    result = runner.invoke(
        app, ["scan", str(_project(tmp_path, "import json\n")), "--target", "v16"]
    )
    assert result.exit_code == 0


def test_finding_exits_1(tmp_path: Path) -> None:
    """An error finding means exit code 1."""
    result = runner.invoke(
        app, ["scan", str(_project(tmp_path, "import imp\n")), "--target", "v16"]
    )
    assert result.exit_code == 1
    assert "v16-removed-python-stdlib" in result.output


def test_fail_on_never(tmp_path: Path) -> None:
    """--fail-on never always exits 0."""
    args = [
        "scan",
        str(_project(tmp_path, "import imp\n")),
        "--target",
        "v16",
        "--fail-on",
        "never",
    ]
    assert runner.invoke(app, args).exit_code == 0


def test_unknown_target_exits_2(tmp_path: Path) -> None:
    """An unknown target is a usage error."""
    result = runner.invoke(app, ["scan", str(tmp_path), "--target", "v99"])
    assert result.exit_code == 2


def test_missing_path_exits_2(tmp_path: Path) -> None:
    """A missing path is a usage error."""
    result = runner.invoke(app, ["scan", str(tmp_path / "nope"), "--target", "v16"])
    assert result.exit_code == 2


def test_json_format(tmp_path: Path) -> None:
    """--format json prints valid JSON with the finding."""
    args = ["scan", str(_project(tmp_path, "import imp\n")), "--target", "v16", "--format", "json"]
    result = runner.invoke(app, args)
    data = json.loads(result.output)
    assert data["target"] == "v16"
    assert data["result"]["findings"][0]["rule_id"] == "v16-removed-python-stdlib"


def test_syntax_error_file_is_listed_not_crashing(tmp_path: Path) -> None:
    """An unparsable file is reported under 'Not checked'."""
    result = runner.invoke(app, ["scan", str(_project(tmp_path, "def (:\n")), "--target", "v16"])
    assert result.exit_code == 0
    assert "syntax error" in result.output
