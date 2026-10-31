"""Tests for the override_doctype_class hook rules."""

from collections import Counter
from pathlib import Path

from tminus.engine.loader import load_rules
from tminus.engine.runner import scan_path

FIXTURES = Path(__file__).parent / "fixtures"
RULES = load_rules("v16")
NO_BASE = "v16-override-doctype-class-no-base"
UNREADABLE = "v16-override-doctype-class-unreadable"
PERM_UNREADABLE = "v16-has-permission-hook-unreadable"


def _make_app(tmp_path: Path, hooks: str, module: str) -> Path:
    """Create a tiny app `myapp` with a hooks.py and one module `mod.py`."""
    pkg = tmp_path / "myapp"
    pkg.mkdir()
    (pkg / "hooks.py").write_text(hooks)
    (pkg / "mod.py").write_text(module)
    return tmp_path


def test_bad_app_findings() -> None:
    """Two classes without a real base and two unresolved targets."""
    result = scan_path(FIXTURES / "overrides_bad", RULES)
    assert Counter(f.rule_id for f in result.findings) == {NO_BASE: 2, UNREADABLE: 2}


def test_bad_app_points_at_class_lines() -> None:
    """Findings for missing bases point at the class definitions."""
    result = scan_path(FIXTURES / "overrides_bad", RULES)
    lines = sorted(f.line for f in result.findings if f.rule_id == NO_BASE)
    assert lines == [1, 10]


def test_clean_app_has_no_findings() -> None:
    """Real base classes, a mixin and a list-valued hook are all fine."""
    assert scan_path(FIXTURES / "overrides_clean", RULES).findings == []


def test_ignore_comment_on_class_line(tmp_path: Path) -> None:
    """An ignore comment on the class line suppresses the finding."""
    hooks = 'override_doctype_class = {"ToDo": "myapp.mod.C"}\n'
    root = _make_app(tmp_path, hooks, f"class C:  # tminus: ignore[{NO_BASE}]\n    pass\n")
    assert scan_path(root, RULES).findings == []


def test_function_instead_of_class_is_unreadable(tmp_path: Path) -> None:
    """A class hook that points at a function cannot be checked."""
    hooks = 'override_doctype_class = {"ToDo": "myapp.mod.f"}\n'
    root = _make_app(tmp_path, hooks, "def f():\n    pass\n")
    assert [f.rule_id for f in scan_path(root, RULES).findings] == [UNREADABLE]


def test_class_instead_of_function_is_unreadable(tmp_path: Path) -> None:
    """A has_permission hook that points at a class cannot be checked."""
    hooks = 'has_permission = {"ToDo": "myapp.mod.C"}\n'
    root = _make_app(tmp_path, hooks, "class C:\n    pass\n")
    assert [f.rule_id for f in scan_path(root, RULES).findings] == [PERM_UNREADABLE]


def test_non_literal_override_table_is_listed(tmp_path: Path) -> None:
    """A table built at run time is reported as not checked."""
    root = _make_app(tmp_path, "override_doctype_class = build()\n", "x = 1\n")
    result = scan_path(root, RULES)
    assert result.findings == []
    assert any("override_doctype_class is not a literal dict" in n for n in result.skipped)
