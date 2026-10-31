"""Tests for resolving local names back to their import paths."""

import ast

from tminus.engine.names import build_alias_table, resolve


def _resolve(source: str, expr: str) -> str | None:
    """Build the alias table for `source` and resolve the expression `expr`."""
    table = build_alias_table(ast.parse(source))
    return resolve(ast.parse(expr, mode="eval").body, table)


def test_from_import() -> None:
    """`from a.b import c` makes `c` mean a.b.c."""
    assert _resolve("from a.b import c\n", "c") == "a.b.c"


def test_from_import_with_alias() -> None:
    """`from a.b import c as d` makes `d` mean a.b.c."""
    assert _resolve("from a.b import c as d\n", "d") == "a.b.c"


def test_import_as() -> None:
    """`import a.b as x` makes `x.f` mean a.b.f."""
    assert _resolve("import a.b as x\n", "x.f") == "a.b.f"


def test_plain_dotted_import_binds_top_package() -> None:
    """`import a.b.c` binds `a`, so `a.b.c.f` resolves to itself."""
    assert _resolve("import a.b.c\n", "a.b.c.f") == "a.b.c.f"


def test_module_imported_from_package() -> None:
    """`from a import b` then `b.f` resolves to a.b.f."""
    assert _resolve("from a import b\n", "b.f") == "a.b.f"


def test_unknown_name() -> None:
    """A name that was never imported does not resolve."""
    assert _resolve("import a\n", "other.f") is None


def test_relative_and_star_imports_are_ignored() -> None:
    """Relative imports and `*` imports add nothing to the table."""
    assert _resolve("from . import x\nfrom a import *\n", "x") is None


def test_function_level_import_counts() -> None:
    """An import inside a function is still recorded (scope-insensitive)."""
    assert _resolve("def f():\n    from a import b\n", "b") == "a.b"
