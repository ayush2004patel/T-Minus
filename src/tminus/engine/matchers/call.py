"""Matcher for functions that were removed or whose call signature changed."""

from __future__ import annotations

import ast

from tminus.engine.context import FileContext
from tminus.engine.guards import is_guarded
from tminus.engine.models import CallMatch, Hit, Rule


def _removed_lines(ctx: FileContext, paths: set[str]) -> list[int]:
    """Lines that import or reach a removed function (from-imports and module attributes)."""
    lines = [  # `from a.b import f`: the import itself fails on v16
        node.lineno
        for node in ctx.from_imports
        if node.level == 0
        and node.module
        and any(f"{node.module}.{a.name}" in paths for a in node.names)
    ]
    lines += [line for line, path in ctx.attr_paths if path in paths]  # e.g. `u.f(...)`
    return lines


def _name_of(node: ast.expr) -> str | None:
    """The last name of an expression: `taxes` for both `taxes` and `doc.taxes`."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_old_style(call: ast.Call, match: CallMatch) -> bool:
    """True if this call to a changed function still uses the v15 form."""
    if match.check == "keyword_only":  # v16 signature starts with `*`
        return bool(call.args)
    if match.check == "positional_count":  # v16 added a required argument
        starred = any(isinstance(a, ast.Starred) for a in call.args)
        return len(call.args) == match.count and not starred and not call.keywords
    if match.check == "first_arg_named":  # first argument changed meaning
        first = _name_of(call.args[0]) if call.args else None
        return first in match.names or any(k.arg in match.names for k in call.keywords)
    return False


def match_call(ctx: FileContext, rule: Rule) -> list[Hit]:
    """Return line numbers of uses that break on v16; guarded compat code is skipped."""
    match = rule.match
    if not isinstance(match, CallMatch):  # wrong rule type for this matcher
        return []
    paths = set(match.paths)
    if match.check == "removed":
        lines = _removed_lines(ctx, paths)
    else:
        lines = [
            call.lineno
            for call, path in ctx.calls
            if path is not None and path in paths and _is_old_style(call, match)
        ]
    kept = sorted({line for line in lines if not is_guarded(line, ctx.guarded)})
    return [Hit(line=line) for line in kept]
