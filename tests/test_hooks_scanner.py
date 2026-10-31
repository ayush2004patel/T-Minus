"""Tests for the hooks.py app-level scanner."""

from collections import Counter
from pathlib import Path

from typer.testing import CliRunner

from tminus.cli.main import app
from tminus.engine.loader import load_rules
from tminus.engine.runner import scan_path

FIXTURES = Path(__file__).parent / "fixtures"
RULES = load_rules("v16")
NONE_RULE = "v16-has-permission-hook-returns-none"
UNREADABLE_RULE = "v16-has-permission-hook-unreadable"


def _make_app(tmp_path: Path, hooks: str, files: dict[str, str]) -> Path:
    """Create a tiny app package `myapp` with the given hooks.py and extra files."""
    pkg = tmp_path / "myapp"
    pkg.mkdir()
    (pkg / "hooks.py").write_text(hooks)
    for name, content in files.items():
        target = pkg / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return tmp_path


def test_bad_app_findings() -> None:
    """The bad fixture app gives three returns-None errors and two unreadable warnings."""
    result = scan_path(FIXTURES / "app_bad", RULES)
    assert Counter(f.rule_id for f in result.findings) == {NONE_RULE: 3, UNREADABLE_RULE: 2}


def test_bad_app_report_lines() -> None:
    """Lines point at the function problem, not at hooks.py."""
    result = scan_path(FIXTURES / "app_bad", RULES)
    none_lines = {Path(f.file).name: f.line for f in result.findings if f.rule_id == NONE_RULE}
    assert none_lines["permissions.py"] in {1, 8, 12}
    assert all(f.detail.startswith("has_permission[") for f in result.findings)


def test_clean_app_has_no_findings() -> None:
    """The clean fixture app is clean, including a list-valued hook."""
    assert scan_path(FIXTURES / "app_clean", RULES).findings == []


def test_non_literal_hook_is_listed_not_checked(tmp_path: Path) -> None:
    """A hook table built by a function call is reported as not checked."""
    root = _make_app(tmp_path, "has_permission = build()\n", {})
    result = scan_path(root, RULES)
    assert result.findings == []
    assert any("not a literal dict" in note for note in result.skipped)


def test_package_module_resolves(tmp_path: Path) -> None:
    """A function inside `perms/__init__.py` is found."""
    hooks = 'has_permission = {"Customer": "myapp.perms.check"}\n'
    root = _make_app(
        tmp_path, hooks, {"perms/__init__.py": "def check(doc, ptype, user):\n    pass\n"}
    )
    result = scan_path(root, RULES)
    assert [f.rule_id for f in result.findings] == [NONE_RULE]


def test_ignore_comment_on_def_line(tmp_path: Path) -> None:
    """An ignore comment on the def line suppresses the finding."""
    hooks = 'has_permission = {"Customer": "myapp.perms.check"}\n'
    perms = f"def check(doc, ptype, user):  # tminus: ignore[{NONE_RULE}]\n    pass\n"
    root = _make_app(tmp_path, hooks, {"perms.py": perms})
    assert scan_path(root, RULES).findings == []


def test_no_hooks_file_no_findings(tmp_path: Path) -> None:
    """A folder without hooks.py is simply clean for hook rules."""
    (tmp_path / "x.py").write_text("x = 1\n")
    assert scan_path(tmp_path, RULES).findings == []


def test_cli_exit_code_on_bad_app() -> None:
    """The CLI fails (exit 1) on the bad app and prints which hook is at fault."""
    result = CliRunner().invoke(app, ["scan", str(FIXTURES / "app_bad"), "--target", "v16"])
    assert result.exit_code == 1
    assert 'has_permission["Customer"]' in result.output
