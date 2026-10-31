"""Resolve names in a Python file back to the dotted path they were imported from."""

from __future__ import annotations

import ast


def build_alias_table(tree: ast.AST) -> dict[str, str]:
    """Map each name bound by an import to the dotted path it refers to."""
    table: dict[str, str] = {}
    for node in ast.walk(tree):  # scope-insensitive: function-level imports count too
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:  # `import a.b as x` binds x to a.b
                    table[alias.asname] = alias.name
                else:  # `import a.b.c` binds only the top package `a`
                    top = alias.name.split(".")[0]
                    table[top] = top
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                if alias.name != "*":
                    table[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return table


def resolve(node: ast.expr, table: dict[str, str]) -> str | None:
    """Dotted path an expression refers to (e.g. `u.f` -> `a.b.f`), or None if unknown."""
    if isinstance(node, ast.Name):
        return table.get(node.id)
    if isinstance(node, ast.Attribute):
        base = resolve(node.value, table)
        return f"{base}.{node.attr}" if base else None
    return None
