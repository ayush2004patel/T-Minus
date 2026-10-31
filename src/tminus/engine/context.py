"""Per-file facts computed once and shared by every matcher."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from tminus.engine.guards import guarded_ranges
from tminus.engine.names import build_alias_table, resolve


@dataclass(frozen=True)
class FileContext:
    """The parsed file plus lookups that many rules need."""

    tree: ast.AST
    aliases: dict[str, str]  # local name -> dotted import path
    guarded: list[tuple[int, int]]  # line ranges protected by try/except ImportError
    from_imports: list[ast.ImportFrom]
    calls: list[tuple[ast.Call, str | None]]  # each call and the dotted path it calls
    attr_paths: list[tuple[int, str]]  # (line, dotted path) of resolvable attribute chains

    @classmethod
    def build(cls, tree: ast.AST) -> FileContext:
        """Walk the tree once and collect everything the matchers will ask for."""
        aliases = build_alias_table(tree)
        from_imports: list[ast.ImportFrom] = []
        calls: list[tuple[ast.Call, str | None]] = []
        attr_paths: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                from_imports.append(node)
            elif isinstance(node, ast.Call):
                calls.append((node, resolve(node.func, aliases)))
            elif isinstance(node, ast.Attribute):
                path = resolve(node, aliases)
                if path is not None:
                    attr_paths.append((node.lineno, path))
        return cls(tree, aliases, guarded_ranges(tree), from_imports, calls, attr_paths)
