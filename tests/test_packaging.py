"""Tests for the app packaging compatibility rules."""

from pathlib import Path

from typer.testing import CliRunner

from tminus.cli.main import app as cli
from tminus.engine.loader import load_rules
from tminus.engine.models import Finding
from tminus.engine.runner import scan_path

RULES = load_rules("v16")
PY = "v16-app-requires-python"
BOUND = "v16-app-frappe-bound"
MISSING = "v16-app-frappe-bound-missing"
PINS = "v16-app-dependency-pins"
NODE = "v16-app-node-engine"

CLEAN_TOML = (
    '[project]\nname = "x"\nrequires-python = ">=3.10"\ndependencies = []\n\n'
    '[tool.bench.frappe-dependencies]\nfrappe = ">=16.0.0,<17.0.0"\n'
)


def _make(tmp_path: Path, files: dict[str, str], app_dir: str = "myapp") -> Path:
    """Create an app repository: <app_dir>/<app_dir>/hooks.py plus the given root files."""
    repo = tmp_path / app_dir
    (repo / app_dir).mkdir(parents=True)
    (repo / app_dir / "hooks.py").write_text('app_name = "x"\n')
    for name, content in files.items():
        (repo / name).write_text(content)
    return tmp_path


def _found(root: Path, rule_id: str) -> list[Finding]:
    """Findings of one rule."""
    return [f for f in scan_path(root, RULES).findings if f.rule_id == rule_id]


def test_python_cap_in_pyproject(tmp_path: Path) -> None:
    """requires-python that stops below 3.14 is an error, reported on its line."""
    toml = '[project]\nname = "x"\nrequires-python = ">=3.10,<3.13"\n'
    (found,) = _found(_make(tmp_path, {"pyproject.toml": toml}), PY)
    assert found.severity == "error"
    assert found.line == 3
    assert "excludes 3.14" in found.detail


def test_open_python_range_is_fine(tmp_path: Path) -> None:
    """requires-python >=3.10 allows 3.14."""
    assert _found(_make(tmp_path, {"pyproject.toml": CLEAN_TOML}), PY) == []


def test_python_cap_in_setup_py(tmp_path: Path) -> None:
    """python_requires in a legacy setup.py is read too."""
    setup = 'from setuptools import setup\nsetup(name="x", python_requires=">=3.8,<3.12")\n'
    assert len(_found(_make(tmp_path, {"setup.py": setup}), PY)) == 1


def test_frappe_bound_excluding_v16(tmp_path: Path) -> None:
    """A bound that stops below 16 is an error."""
    toml = '[tool.bench.frappe-dependencies]\nfrappe = ">=15.0.0,<16.0.0"\n'
    (found,) = _found(_make(tmp_path, {"pyproject.toml": toml}), BOUND)
    assert found.line == 2


def test_frappe_bounds_that_allow_v16(tmp_path: Path) -> None:
    """Open bounds and bounds that start above 16.0 are accepted."""
    for bound in (">=15.0.0", ">=16.50.0,<17.0.0", ">=16.0.0,<17.0.0", ">=15.0.0,<17.0.0"):
        toml = f'[tool.bench.frappe-dependencies]\nfrappe = "{bound}"\n'
        root = _make(
            tmp_path / bound.replace(",", "_").replace(">=", "ge"), {"pyproject.toml": toml}
        )
        assert _found(root, BOUND) == [], bound


def test_missing_frappe_bound_with_pyproject(tmp_path: Path) -> None:
    """No frappe bound is a warning, pointing at pyproject.toml."""
    (found,) = _found(_make(tmp_path, {"pyproject.toml": "[project]\nname = 'x'\n"}), MISSING)
    assert found.severity == "warning"
    assert found.file.endswith("pyproject.toml")


def test_missing_frappe_bound_with_setup_py_only(tmp_path: Path) -> None:
    """An app with only setup.py has no bound either; the finding points at setup.py."""
    (found,) = _found(
        _make(tmp_path, {"setup.py": "from setuptools import setup\nsetup()\n"}), MISSING
    )
    assert found.file.endswith("setup.py")


def test_present_frappe_bound_is_not_missing(tmp_path: Path) -> None:
    """A declared bound silences the missing-bound warning."""
    assert _found(_make(tmp_path, {"pyproject.toml": CLEAN_TOML}), MISSING) == []


def test_dependency_pin_conflict_in_pyproject(tmp_path: Path) -> None:
    """Werkzeug<3 cannot be installed next to frappe's Werkzeug==3.1.9."""
    toml = CLEAN_TOML.replace("dependencies = []", 'dependencies = ["Werkzeug<3"]')
    (found,) = _found(_make(tmp_path, {"pyproject.toml": toml}), PINS)
    assert found.detail.startswith("werkzeug<3 conflicts with frappe's werkzeug==")


def test_dependency_pins_in_requirements_and_setup_py(tmp_path: Path) -> None:
    """requirements.txt and setup.py install_requires are read; comments/options skipped."""
    reqs = "# pins\n-r other.txt\nWerkzeug<3  # old\nrequests>=2\n"
    assert len(_found(_make(tmp_path / "a", {"requirements.txt": reqs}), PINS)) == 1
    setup = 'from setuptools import setup\nsetup(install_requires=["Werkzeug<3", "requests"])\n'
    assert len(_found(_make(tmp_path / "b", {"setup.py": setup}), PINS)) == 1


def test_compatible_and_url_dependencies_are_fine(tmp_path: Path) -> None:
    """Overlapping ranges, unpinned names and direct URL references are not flagged."""
    deps = '["Werkzeug>=3", "requests", "pypika @ git+https://example.com/x.git"]'
    toml = CLEAN_TOML.replace("dependencies = []", f"dependencies = {deps}")
    assert _found(_make(tmp_path, {"pyproject.toml": toml}), PINS) == []


def test_node_engine(tmp_path: Path) -> None:
    """engines.node that excludes 24 is a warning; ones that allow it are fine."""
    bad = '{\n  "engines": { "node": "<=20" }\n}\n'
    (found,) = _found(
        _make(tmp_path / "a", {"pyproject.toml": CLEAN_TOML, "package.json": bad}), NODE
    )
    assert found.line == 2
    good = '{"engines": {"node": ">=18"}}'
    assert (
        _found(_make(tmp_path / "b", {"pyproject.toml": CLEAN_TOML, "package.json": good}), NODE)
        == []
    )
    odd = '{"engines": {"node": "14 - 20"}}'
    assert (
        _found(_make(tmp_path / "c", {"pyproject.toml": CLEAN_TOML, "package.json": odd}), NODE)
        == []
    )


def test_upstream_apps_are_skipped(tmp_path: Path) -> None:
    """frappe, erpnext and hrms are installed from their own version-16 branch."""
    toml = '[tool.bench.frappe-dependencies]\nfrappe = ">=15.0.0,<16.0.0"\n'
    assert _found(_make(tmp_path, {"pyproject.toml": toml}, app_dir="erpnext"), BOUND) == []


def test_app_without_packaging_files_is_listed(tmp_path: Path) -> None:
    """An app folder with no packaging file is reported as not checked."""
    result = scan_path(_make(tmp_path, {}), RULES)
    assert any("packaging not checked" in note for note in result.skipped)


def test_ignore_comment_in_pyproject(tmp_path: Path) -> None:
    """A # tminus: ignore[...] comment on the offending line suppresses the finding."""
    toml = f'[project]\nrequires-python = "<3.13"  # tminus: ignore[{PY}]\n'
    assert _found(_make(tmp_path, {"pyproject.toml": toml}), PY) == []


def test_cli_fails_on_a_bad_app(tmp_path: Path) -> None:
    """The CLI exits 1 for an app whose frappe bound excludes v16."""
    toml = '[tool.bench.frappe-dependencies]\nfrappe = "<16"\n'
    root = _make(tmp_path, {"pyproject.toml": toml})
    result = CliRunner().invoke(cli, ["scan", str(root), "--target", "v16"])
    assert result.exit_code == 1
    assert "v16-app-frappe-bound" in result.output
