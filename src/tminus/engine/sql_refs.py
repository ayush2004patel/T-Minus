"""Find DocType fields named inside SQL text (frappe.db.sql queries and Script Reports)."""

from __future__ import annotations

import ast
import re

_BACKTICKED = re.compile(r"`tab([^`]+)`(?:\s+(?:as\s+)?(\w+))?", re.IGNORECASE)
_PLAIN = re.compile(r"(?<!`)\btab([A-Z][A-Za-z0-9_]*)\b(?:\s+(?:as\s+)?(\w+))?")
_QUALIFIED = re.compile(r"(?:`tab([^`]+)`|(?<![\w`.])(\w+))\s*\.\s*`?(\w+)`?")
_TOKEN = re.compile(r"(?<![\w.`])([A-Za-z_]\w*)(?!\s*\()")
_LITERAL = re.compile(r"'[^']*'|\"[^\"]*\"")
_AS_BEFORE = re.compile(r"\bas\s+$", re.IGNORECASE)
_KEYWORDS = {
    "where", "on", "join", "left", "right", "inner", "outer", "cross", "group", "order",
    "limit", "set", "using", "and", "or", "union", "select", "values", "from", "having",
    "as", "into", "update", "delete", "natural", "straight_join",
}  # fmt: skip


def _leaf_text(node: ast.AST) -> str:
    """Text of a string piece; anything that is not a literal string becomes `{}`."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(_leaf_text(v) for v in node.values)
    return "{}"


def _flatten_add(node: ast.AST) -> list[ast.AST]:
    """The pieces of `a + b + c`, left to right."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return [*_flatten_add(node.left), *_flatten_add(node.right)]
    return [node]


def sql_text(node: ast.AST, consumed: set[int]) -> str | None:
    """The text of a string-like node (literal, f-string, or `"..." + "..."`), else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        consumed.update(id(v) for v in node.values)
        return _leaf_text(node)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        parts = _flatten_add(node)
        if any(isinstance(p, ast.JoinedStr) or _leaf_text(p) != "{}" for p in parts):
            consumed.update(id(n) for n in ast.walk(node) if n is not node)
            return "".join(_leaf_text(p) for p in parts)
    return None


def _blank(text: str, pattern: re.Pattern[str]) -> str:
    """Replace every match with spaces so that offsets (and line numbers) stay the same."""
    return pattern.sub(lambda m: " " * len(m.group(0)), text)


def sql_refs(text: str, line: int) -> list[tuple[str, str, int]]:
    """(DocType, field, line) for columns named in this SQL text."""
    masked = _blank(text, _LITERAL)  # ignore quoted values such as 'source'
    aliases: dict[str, str] = {}
    tables: set[str] = set()
    for pattern in (_BACKTICKED, _PLAIN):
        for m in pattern.finditer(masked):
            tables.add(m.group(1))
            alias = m.group(2)
            if alias and alias.lower() not in _KEYWORDS:
                aliases[alias] = m.group(1)
    if not tables:
        return []
    found: set[tuple[str, str, int]] = set()
    for m in _QUALIFIED.finditer(masked):  # alias.field or `tabX`.field
        qualifier = m.group(2)
        if m.group(1):
            doctype: str | None = m.group(1)
        elif qualifier in aliases:
            doctype = aliases[qualifier]
        elif qualifier.startswith("tab") and qualifier[3:] in tables:
            doctype = qualifier[3:]
        else:
            doctype = None
        if doctype:
            found.add((doctype, m.group(3), line + text.count("\n", 0, m.start(3))))
    if len(tables) == 1:  # one table: bare column names belong to it
        only = next(iter(tables))
        scan = _blank(_blank(masked, _BACKTICKED), _PLAIN)
        for m in _TOKEN.finditer(scan):
            word = m.group(1)
            before = scan[max(0, m.start() - 12) : m.start()]
            if word.lower() in _KEYWORDS or _AS_BEFORE.search(before):
                continue  # a keyword, or an alias introduced with AS
            found.add((only, word, line + text.count("\n", 0, m.start())))
    return sorted(found)
