"""Find places where code names a DocType and one of its fields (or just a DocType)."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import NamedTuple

from tminus.engine.names import resolve


class FieldRef(NamedTuple):
    """A field of a known DocType that the code reads, filters on or writes."""

    doctype: str
    name: str
    line: int


@dataclass(frozen=True)
class Slots:
    """Where an API call keeps its field names: positions and keyword names."""

    filters_pos: int | None = None  # positional index of a filters argument
    filters_kw: tuple[str, ...] = ()
    fields_pos: int | None = None  # positional index of a fields argument
    fields_kw: tuple[str, ...] = ()
    flexible_pos: tuple[int, ...] = ()  # positions that hold filters OR fields (get_all style)


_GET_LIST = Slots(
    filters_kw=("filters", "or_filters"),
    fields_kw=("fields", "order_by", "group_by", "pluck"),
    flexible_pos=(1, 2),  # frappe accepts (doctype, fields, filters) in either order
)
_SINGLE = Slots(fields_pos=1, fields_kw=("field", "fieldname"))
_VALUE = Slots(filters_pos=1, filters_kw=("filters",), fields_pos=2, fields_kw=("fieldname",))
_FILTERS = Slots(filters_pos=1, filters_kw=("filters",))

API_SLOTS: dict[str, Slots] = {
    "frappe.db.get_value": _VALUE,
    "frappe.db.get_values": _VALUE,
    "frappe.db.set_value": _VALUE,
    "frappe.db.get_single_value": _SINGLE,
    "frappe.get_single_value": _SINGLE,
    "frappe.db.set_single_value": _SINGLE,
    "frappe.get_all": _GET_LIST,
    "frappe.get_list": _GET_LIST,
    "frappe.db.get_list": _GET_LIST,
    "frappe.db.exists": _FILTERS,
    "frappe.db.count": _FILTERS,
    "frappe.db.delete": _FILTERS,
}

# Calls that return a document of a known DocType (first argument is the DocType name).
DOC_FACTORIES = {
    "frappe.get_doc",
    "frappe.get_cached_doc",
    "frappe.new_doc",
    "frappe.get_last_doc",
    "frappe.get_single",
}

# Calls whose first argument is a DocType name.
DOCTYPE_FIRST_ARG_APIS = (
    set(API_SLOTS)
    | DOC_FACTORIES
    | {
        "frappe.get_meta",
        "frappe.delete_doc",
        "frappe.rename_doc",
        "frappe.reload_doctype",
        "frappe.qb.DocType",
    }
)

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DOC_METHODS = {"get", "set", "db_set"}  # doc.get("field"), doc.set("field", v)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _str(node: ast.expr) -> str | None:
    """The value of a string literal, or None."""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _names_from(expr: ast.expr, as_filters: bool) -> list[tuple[str, int]]:
    """Candidate field names in a fields/filters argument, with their line numbers."""
    out: list[tuple[str, int]] = []
    text = _str(expr)
    if text is not None:
        if not as_filters:  # a plain string is a field list ("a, b desc"), not a filter
            out += [(t, expr.lineno) for t in _TOKEN.findall(text)]
    elif isinstance(expr, ast.Dict):  # {"field": value}: the keys are field names
        for key in expr.keys:
            key_text = _str(key) if key is not None else None
            if key_text is not None and key is not None:
                out += [(t, key.lineno) for t in _TOKEN.findall(key_text)]
    elif isinstance(expr, ast.List | ast.Tuple):
        for item in expr.elts:
            item_text = _str(item)
            if item_text is not None and not as_filters:
                out += [(t, item.lineno) for t in _TOKEN.findall(item_text)]
            elif isinstance(item, ast.List | ast.Tuple) and len(item.elts) in (3, 4):
                # filter triple [field, op, value] or [doctype, field, op, value]
                field = _str(item.elts[1 if len(item.elts) == 4 else 0])
                if field is not None:
                    out += [(t, item.lineno) for t in _TOKEN.findall(field)]
    return out


def _is_field_list(expr: ast.expr) -> bool:
    """True if a positional argument looks like a fields list rather than filters."""
    if _str(expr) is not None:
        return True
    if isinstance(expr, ast.List | ast.Tuple):
        return bool(expr.elts) and all(_str(e) is not None for e in expr.elts)
    return False


def _literal_doctype(call: ast.Call) -> str | None:
    """The DocType named by the first argument (or `doctype=`), if it is a string literal."""
    if call.args:
        return _str(call.args[0])
    for kw in call.keywords:
        if kw.arg == "doctype":
            return _str(kw.value)
    return None


def _call_refs(call: ast.Call, path: str) -> list[FieldRef]:
    """Field references inside one database/list API call."""
    slots = API_SLOTS.get(path)
    doctype = _literal_doctype(call)
    if slots is None or doctype is None:
        return []
    found: list[tuple[str, int]] = []
    for pos, args in ((slots.filters_pos, True), (slots.fields_pos, False)):
        if pos is not None and len(call.args) > pos:
            found += _names_from(call.args[pos], as_filters=args)
    for pos in slots.flexible_pos:
        if len(call.args) > pos:
            arg = call.args[pos]
            found += _names_from(arg, as_filters=not _is_field_list(arg))
    for kw in call.keywords:
        if kw.arg in slots.filters_kw:
            found += _names_from(kw.value, as_filters=True)
        elif kw.arg in slots.fields_kw:
            found += _names_from(kw.value, as_filters=False)
    return [FieldRef(doctype, name, line) for name, line in found]


def _dict_doctype(node: ast.Dict) -> str | None:
    """The DocType a dict literal describes (`{"doctype": "Asset", ...}`), if any."""
    for key, value in zip(node.keys, node.values, strict=True):
        if key is not None and _str(key) == "doctype":
            return _str(value)
    return None


def _factory_doctype(call: ast.Call, aliases: dict[str, str]) -> str | None:
    """The DocType returned by frappe.get_doc("X", ...) and similar calls."""
    if resolve(call.func, aliases) not in DOC_FACTORIES or not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Dict):
        return _dict_doctype(first)
    return _str(first)


def _scope_nodes(scope: ast.AST) -> list[ast.AST]:
    """Nodes that belong directly to this scope (nested functions and classes excluded)."""
    nodes: list[ast.AST] = []
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        nodes.append(node)
        if not isinstance(node, _SCOPES):  # a nested scope is analysed on its own
            stack.extend(ast.iter_child_nodes(node))
    return nodes


def _typed_variables(
    scope: ast.AST, nodes: list[ast.AST], aliases: dict[str, str]
) -> dict[str, str]:
    """Variables that hold exactly one known DocType's document in this scope."""
    assigned: dict[str, set[str]] = {}
    unknown: set[str] = set()  # names also assigned from something we cannot type
    for node in nodes:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            doctype = (
                _factory_doctype(node.value, aliases) if isinstance(node.value, ast.Call) else None
            )
            if doctype is None:
                unknown.add(target.id)
            else:
                assigned.setdefault(target.id, set()).add(doctype)
        elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            unknown.add(node.target.id)
    params: set[str] = set()
    if isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef):
        args = scope.args
        params = {a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]}
        params |= {a.arg for a in (args.vararg, args.kwarg) if a is not None}
    return {
        name: next(iter(types))
        for name, types in assigned.items()
        if len(types) == 1 and name not in unknown and name not in params
    }


def _doc_doctype(expr: ast.expr, variables: dict[str, str], aliases: dict[str, str]) -> str | None:
    """The DocType of an expression that is a typed variable or a get_doc(...) call."""
    if isinstance(expr, ast.Name):
        return variables.get(expr.id)
    if isinstance(expr, ast.Call):
        return _factory_doctype(expr, aliases)
    return None


def _scope_refs(scope: ast.AST, aliases: dict[str, str]) -> list[FieldRef]:
    """Field references through typed documents inside one scope."""
    nodes = _scope_nodes(scope)
    variables = _typed_variables(scope, nodes, aliases)
    refs: list[FieldRef] = []
    for node in nodes:
        if isinstance(node, ast.Attribute):  # doc.field
            doctype = _doc_doctype(node.value, variables, aliases)
            if doctype:
                refs.append(FieldRef(doctype, node.attr, node.lineno))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _DOC_METHODS and node.args:  # doc.get("field")
                doctype = _doc_doctype(node.func.value, variables, aliases)
                name = _str(node.args[0])
                if doctype and name:
                    refs.append(FieldRef(doctype, name, node.lineno))
        elif isinstance(node, ast.Subscript):  # doc["field"]
            doctype = _doc_doctype(node.value, variables, aliases)
            name = _str(node.slice)
            if doctype and name:
                refs.append(FieldRef(doctype, name, node.lineno))
        elif isinstance(node, ast.Dict):  # {"doctype": "Asset", "field": value}
            doctype = _dict_doctype(node)
            if doctype:
                refs += [
                    FieldRef(doctype, key_text, key.lineno)
                    for key in node.keys
                    if key is not None and (key_text := _str(key)) is not None
                ]
    return refs


def collect_refs(
    tree: ast.AST, aliases: dict[str, str], calls: list[tuple[ast.Call, str | None]]
) -> tuple[list[FieldRef], list[tuple[str, int]]]:
    """All field references and DocType-name references in a file."""
    field_refs: list[FieldRef] = []
    doctype_refs: list[tuple[str, int]] = []
    for call, path in calls:
        if path is None:
            continue
        field_refs += _call_refs(call, path)
        if path in DOCTYPE_FIRST_ARG_APIS:
            name = _literal_doctype(call)
            if name is not None:
                doctype_refs.append((name, call.lineno))
    scopes: list[ast.AST] = [tree]
    scopes += [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
    for scope in scopes:
        field_refs += _scope_refs(scope, aliases)
    for node in ast.walk(tree):  # `{"doctype": "X"}` anywhere names a DocType
        if isinstance(node, ast.Dict):
            doctype = _dict_doctype(node)
            if doctype:
                doctype_refs.append((doctype, node.lineno))
    return field_refs, doctype_refs
