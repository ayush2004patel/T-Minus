"""Decide whether a function can return None, explicitly or by falling off its end."""

from __future__ import annotations

import ast

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
_NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
_LOOPS = (ast.For, ast.AsyncFor, ast.While)
_INNER_SCOPES = _LOOPS + _NESTED  # a break in these belongs to them, not to our loop


def _explicit_none_returns(body: list[ast.stmt]) -> list[int]:
    """Lines of `return` / `return None` in this function, ignoring nested functions."""
    lines: list[int] = []
    stack: list[ast.AST] = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, _NESTED):  # a nested function's returns are not ours
            continue
        if isinstance(node, ast.Return) and (
            node.value is None
            or (isinstance(node.value, ast.Constant) and node.value.value is None)
        ):
            lines.append(node.lineno)
        stack.extend(ast.iter_child_nodes(node))
    return sorted(lines)


def _has_break(body: list[ast.stmt]) -> bool:
    """True if a `break` in this loop body belongs to this loop (not an inner one)."""
    stack: list[ast.AST] = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Break):
            return True
        if isinstance(node, _INNER_SCOPES):
            continue
        stack.extend(ast.iter_child_nodes(node))
    return False


def _try_falls_through(node: ast.Try | ast.TryStar) -> bool:
    """Can control leave this try statement normally?"""
    normal = _falls_through(node.body) and _falls_through(node.orelse)
    handled = any(_falls_through(h.body) for h in node.handlers)
    if node.finalbody and not _falls_through(node.finalbody):  # finally always returns/raises
        return False
    return normal or handled


def _stmt_falls_through(stmt: ast.stmt) -> bool:
    """Can control reach the statement after this one?"""
    if isinstance(stmt, ast.Return | ast.Raise):
        return False
    if isinstance(stmt, ast.If):  # falls through if either branch does (empty else counts)
        return _falls_through(stmt.body) or _falls_through(stmt.orelse)
    if isinstance(stmt, ast.With | ast.AsyncWith):
        return _falls_through(stmt.body)
    if isinstance(stmt, ast.Try | ast.TryStar):
        return _try_falls_through(stmt)
    if isinstance(stmt, ast.While):  # `while True` without break never ends normally
        forever = isinstance(stmt.test, ast.Constant) and bool(stmt.test.value)
        return not (forever and not _has_break(stmt.body))
    if isinstance(stmt, ast.Match):
        wildcard = any(
            isinstance(c.pattern, ast.MatchAs) and c.pattern.pattern is None and c.guard is None
            for c in stmt.cases
        )
        return not wildcard or any(_falls_through(c.body) for c in stmt.cases)
    return True  # plain statements, loops that may run zero times, etc.


def _falls_through(stmts: list[ast.stmt]) -> bool:
    """True if control can reach the end of this block without returning or raising."""
    return all(_stmt_falls_through(s) for s in stmts)


def can_return_none(func: FunctionNode) -> int | None:
    """Return the line to report if the function can return None, else None."""
    explicit = _explicit_none_returns(func.body)
    if explicit:
        return explicit[0]  # point at the first `return` / `return None`
    if _falls_through(func.body):
        return func.lineno  # no return on some path: point at the def line
    return None
