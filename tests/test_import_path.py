"""Tests for the import_path matcher and scanner behaviour."""

from tminus.engine.loader import load_rules
from tminus.engine.scanners.python_ast import scan_source

RULES = load_rules("v16")


def _lines(source: str) -> list[int]:
    """Return finding line numbers for a source snippet."""
    return [f.line for f in scan_source(source, "x.py", RULES)]


def test_plain_import() -> None:
    """`import imp` is flagged."""
    assert _lines("import imp\n") == [1]


def test_from_import_and_submodule() -> None:
    """`from imp import x` and `import distutils.core` are flagged."""
    assert _lines("from imp import reload\nimport distutils.core\n") == [1, 2]


def test_guarded_import_skipped() -> None:
    """An import inside try/except ImportError is not flagged."""
    assert _lines("try:\n    import imp\nexcept ImportError:\n    imp = None\n") == []


def test_guard_with_tuple_and_module_not_found() -> None:
    """Tuples and ModuleNotFoundError also count as guards."""
    src = "try:\n    import cgi\nexcept (OSError, ModuleNotFoundError):\n    pass\n"
    assert _lines(src) == []


def test_other_except_does_not_guard() -> None:
    """A try with an unrelated except still flags the import."""
    assert _lines("try:\n    import imp\nexcept ValueError:\n    pass\n") == [2]


def test_import_in_except_branch_is_flagged() -> None:
    """The fallback import inside the handler is still scanned."""
    src = "try:\n    import json\nexcept ImportError:\n    import imp\n"
    assert _lines(src) == [4]


def test_ignore_comment() -> None:
    """A tminus ignore comment suppresses that rule on that line."""
    assert _lines("import imp  # tminus: ignore[v16-removed-python-stdlib]\n") == []


def test_ignore_comment_other_rule_does_not_suppress() -> None:
    """Ignoring a different rule id does not hide the finding."""
    assert _lines("import imp  # tminus: ignore[other-rule]\n") == [1]


def test_relative_and_unrelated_imports() -> None:
    """Relative imports and unrelated modules are clean."""
    assert _lines("from . import imp\nimport json\n") == []
