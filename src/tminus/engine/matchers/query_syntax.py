"""Matcher for frappe.get_all / get_list calls: SQL strings v16 rejects, unordered first rows."""

from __future__ import annotations

import ast
import re
from collections import Counter

from tminus.engine.context import FileContext
from tminus.engine.frappe_refs import _scope_nodes as scope_nodes
from tminus.engine.models import Hit, QuerySyntaxMatch, Rule

GET_LIST_PATHS = {"frappe.get_all", "frappe.get_list", "frappe.db.get_all", "frappe.db.get_list"}
LIMIT_KEYWORDS = {"limit", "limit_page_length", "page_length"}
OPERATORS = {"=", "!=", ">", "<", ">=", "<=", "like", "not like", "in", "not in", "is", "between"}

# The next three patterns are copied from frappe 16.54.0 frappe/database/query.py, so that this
# check rejects exactly what v16 rejects.
COMMA_PATTERN = re.compile(r",\s*(?![^()]*\))")
FUNCTION_CALL_PATTERN = re.compile(r"^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\(", flags=re.ASCII)
ALLOWED_FIELD_PATTERN = re.compile(
    r"^(?:(`[\w\s-]+`|\w+)\.)?(`\w+`|\w+)(?:\s+as\s+(?:`[\w\s-]+`|'[\w\s:-]+'|\w+))?$",
    flags=re.IGNORECASE,
)


def _text(node: ast.expr) -> str | None:
    """The value of a string literal, or None."""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def select_problem(item: str) -> str | None:
    """What v16 would say about one SELECT field string, or None if it is accepted."""
    if item == "*" or item.isdigit():
        return None
    if FUNCTION_CALL_PATTERN.match(item):
        return (
            "SQL functions are not allowed as strings in SELECT; use dict syntax "
            "such as {'COUNT': '*'}"
        )
    if ALLOWED_FIELD_PATTERN.match(item):
        return None
    return "Invalid field format for SELECT; use plain, backticked or table-qualified field names"


def _field_strings(expr: ast.expr) -> list[tuple[str, int]]:
    """Literal strings of a fields argument, split on commas the way Frappe does."""
    pieces: list[ast.expr] = list(expr.elts) if isinstance(expr, ast.List | ast.Tuple) else [expr]
    out: list[tuple[str, int]] = []
    for piece in pieces:
        text = _text(piece)
        if text is not None:
            out += [(p.strip(), piece.lineno) for p in COMMA_PATTERN.split(text) if p.strip()]
    return out


def _filter_names(expr: ast.expr) -> list[tuple[str, int]]:
    """Literal field names of a filters argument: dict keys, or the field of [field, op, value]."""
    out: list[tuple[str, int]] = []
    if isinstance(expr, ast.Dict):
        for key in expr.keys:
            name = _text(key) if key is not None else None
            if name is not None and key is not None:
                out.append((name, key.lineno))
    elif isinstance(expr, ast.List | ast.Tuple):
        for item in expr.elts:
            if isinstance(item, ast.List | ast.Tuple) and len(item.elts) in (3, 4):
                name = _text(item.elts[1 if len(item.elts) == 4 else 0])
                if name is not None:
                    out.append((name, item.lineno))
    return out


def _positional_kind(expr: ast.expr) -> str | None:
    """Is a positional argument of get_all a `fields` list or a `filters` object?"""
    if isinstance(expr, ast.Dict):
        return "filters"
    if _text(expr) is not None:
        return "fields"
    if isinstance(expr, ast.List | ast.Tuple) and expr.elts:
        strings = [_text(e) for e in expr.elts]
        if all(s is not None for s in strings):  # all strings: a field list, unless a filter triple
            is_triple = len(strings) in (3, 4) and any(s in OPERATORS for s in strings)
            return None if is_triple else "fields"
        if all(isinstance(e, ast.List | ast.Tuple) for e in expr.elts):
            return "filters"
    return None


def _arguments(call: ast.Call) -> tuple[list[ast.expr], list[ast.expr]]:
    """(fields expressions, filters expressions) of a get_all/get_list call."""
    fields: list[ast.expr] = []
    filters: list[ast.expr] = []
    for kw in call.keywords:
        if kw.arg == "fields":
            fields.append(kw.value)
        elif kw.arg in ("filters", "or_filters"):
            filters.append(kw.value)
    for arg in call.args[1:3]:  # frappe accepts (doctype, fields, filters) in either order
        kind = _positional_kind(arg)
        if kind == "fields":
            fields.append(arg)
        elif kind == "filters":
            filters.append(arg)
    return fields, filters


def _sql_string_hits(ctx: FileContext) -> list[Hit]:
    """SQL written as strings in fields or filter keys of get_all/get_list."""
    hits: dict[tuple[int, str], Hit] = {}
    for call, path in ctx.calls:
        if path not in GET_LIST_PATHS:
            continue
        fields, filters = _arguments(call)
        for expr in fields:
            for item, line in _field_strings(expr):
                if (problem := select_problem(item)) is not None:
                    detail = f'fields "{item}": {problem}'
                    hits[(line, detail)] = Hit(line=line, detail=detail)
        for expr in filters:
            for name, line in _filter_names(expr):
                if "(" in name:
                    detail = f'filters "{name}": SQL expressions are not valid filter fields'
                    hits[(line, detail)] = Hit(line=line, detail=detail)
    return sorted(hits.values(), key=lambda h: (h.line, h.detail))


def _looks_up_by_name(call: ast.Call) -> bool:
    """True if the filters contain a `name` key: a lookup of one record, so order is moot."""
    filters = [k.value for k in call.keywords if k.arg == "filters"]
    filters += [a for a in call.args[1:3] if isinstance(a, ast.Dict)]
    return any(
        isinstance(f, ast.Dict) and any(_text(k) == "name" for k in f.keys if k is not None)
        for f in filters
    )


def _unordered_calls(ctx: FileContext) -> dict[int, ast.Call]:
    """get_all/get_list calls without an order_by (and not a lookup by name), keyed by node id."""
    out: dict[int, ast.Call] = {}
    for call, path in ctx.calls:
        if path not in GET_LIST_PATHS:
            continue
        if any(k.arg == "order_by" or k.arg is None for k in call.keywords):
            continue  # ordered, or built from **kwargs that may contain an order
        if _looks_up_by_name(call):
            continue
        out[id(call)] = call
    return out


def _calls_in_test(expr: ast.expr) -> list[ast.Call]:
    """Calls only tested for truthiness: `if x(...)`, `not x(...)`, `a and x(...)`."""
    if isinstance(expr, ast.Call):
        return [expr]
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        return _calls_in_test(expr.operand)
    if isinstance(expr, ast.BoolOp):
        return [c for value in expr.values for c in _calls_in_test(value)]
    if isinstance(expr, ast.NamedExpr):  # if rows := frappe.get_all(...):
        return _calls_in_test(expr.value)
    return []


def _existence_checks(tree: ast.AST) -> set[int]:
    """Ids of calls used only as a yes/no test, where the order of the rows cannot matter."""
    tests: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If | ast.While | ast.IfExp | ast.Assert):
            tests.append(node.test)
    return {id(call) for test in tests for call in _calls_in_test(test)}


def _doctype_of(call: ast.Call) -> str:
    """The DocType of a call if it is a string literal, else `?`."""
    return (_text(call.args[0]) if call.args else None) or "?"


def _is_first_or_last(index: ast.expr) -> bool:
    """True for the subscripts [0] and [-1] (a minus sign is a separate node in the syntax tree)."""
    if isinstance(index, ast.Constant):
        return index.value == 0
    return (
        isinstance(index, ast.UnaryOp)
        and isinstance(index.op, ast.USub)
        and isinstance(index.operand, ast.Constant)
        and index.operand.value == 1
    )


def _first_row_hits(ctx: FileContext) -> list[Hit]:
    """get_all/get_list results used as "the first row" without an order_by."""
    unordered = _unordered_calls(ctx)
    if not unordered:
        return []
    existence = _existence_checks(ctx.tree)
    hits: dict[int, Hit] = {}

    def add(line: int, call: ast.Call, how: str) -> None:
        """Record one hit per line."""
        hits[line] = Hit(line=line, detail=f"{_doctype_of(call)}: {how} without order_by")

    for call in unordered.values():  # limit 1 (unless the result is only tested for emptiness)
        if id(call) in existence:
            continue
        for kw in call.keywords:
            is_one = isinstance(kw.value, ast.Constant) and kw.value.value == 1
            if kw.arg in LIMIT_KEYWORDS and is_one:
                add(call.lineno, call, "only one row is requested (limit 1)")
    scopes: list[ast.AST] = [ctx.tree]
    scopes += [
        n for n in ast.walk(ctx.tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    for scope in scopes:
        nodes = scope_nodes(scope)
        assignments: Counter[str] = Counter()  # how often each name is assigned in this scope
        candidates: dict[str, ast.Call] = {}  # names assigned from an unordered get_all/get_list
        for node in nodes:  # rows = frappe.get_all(...)
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    assignments[target.id] += 1
                    if isinstance(node.value, ast.Call) and id(node.value) in unordered:
                        candidates[target.id] = node.value
        typed = {name: call for name, call in candidates.items() if assignments[name] == 1}
        for node in nodes:
            if not isinstance(node, ast.Subscript) or not _is_first_or_last(node.slice):
                continue
            if isinstance(node.value, ast.Call) and id(node.value) in unordered:
                add(node.lineno, node.value, "the first/last row is used")
            elif isinstance(node.value, ast.Name) and node.value.id in typed:
                add(node.lineno, typed[node.value.id], "the first/last row is used")
    return sorted(hits.values(), key=lambda h: h.line)


def match_query_syntax(ctx: FileContext, rule: Rule) -> list[Hit]:
    """Run the query_syntax check named by the rule."""
    match = rule.match
    if not isinstance(match, QuerySyntaxMatch):  # wrong rule type for this matcher
        return []
    return _sql_string_hits(ctx) if match.check == "sql_strings" else _first_row_hits(ctx)
