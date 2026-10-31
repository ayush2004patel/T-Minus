"""Matcher for imports of removed or moved modules."""

from __future__ import annotations

import ast

from tminus.engine.context import FileContext
from tminus.engine.guards import catches_import_error
from tminus.engine.models import ImportPathMatch, Rule


class _ImportVisitor(ast.NodeVisitor):
    """Walk the tree and collect lines of matching imports outside guarded try blocks."""

    def __init__(self, modules: set[str]) -> None:
        """Remember which top-level module names to look for."""
        self.modules = modules
        self.guarded = 0  # >0 while inside a try whose except catches ImportError
        self.lines: list[int] = []

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802 (ast naming)
        """Treat the try body as safe when an except clause catches ImportError."""
        if any(catches_import_error(h) for h in node.handlers):
            self.guarded += 1
            for stmt in node.body:
                self.visit(stmt)
            self.guarded -= 1
            for handler in node.handlers:  # handlers, else and finally are still scanned
                self.visit(handler)
            for stmt in node.orelse:
                self.visit(stmt)
            for stmt in node.finalbody:
                self.visit(stmt)
        else:
            self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        """Handle `import a.b` statements."""
        if not self.guarded:
            for alias in node.names:
                if alias.name.split(".")[0] in self.modules:
                    self.lines.append(node.lineno)
                    break  # one finding per statement

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        """Handle `from a.b import c` statements (relative imports are ignored)."""
        if self.guarded or node.level != 0 or not node.module:
            return
        if node.module.split(".")[0] in self.modules:
            self.lines.append(node.lineno)


def match_import_path(ctx: FileContext, rule: Rule) -> list[int]:
    """Return line numbers of imports that hit the rule's module list."""
    if not isinstance(rule.match, ImportPathMatch):  # wrong rule type for this matcher
        return []
    visitor = _ImportVisitor(set(rule.match.modules))
    visitor.visit(ctx.tree)
    return visitor.lines
