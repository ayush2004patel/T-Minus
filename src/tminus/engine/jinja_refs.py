"""Find DocType fields used in Jinja templates by reading the expressions as Python."""

from __future__ import annotations

import ast
import re

from tminus.engine.frappe_refs import FieldRef, collect_refs
from tminus.engine.names import resolve

# {# comment #} | {{ expression }} | {% statement %}  (the dashes trim whitespace in Jinja)
_TAG = re.compile(r"\{#.*?#\}|\{\{-?(.*?)-?\}\}|\{%-?(.*?)-?%\}", re.DOTALL)
_FOR = re.compile(r"^for\s+.+?\s+in\s+(.+)$", re.DOTALL)
_SET = re.compile(r"^set\s+(\w+)\s*=\s*(.+)$", re.DOTALL)
_TILDE = re.compile(r"\s~\s")  # Jinja string concatenation


def _statement(body: str, is_block: bool) -> str | None:
    """Turn the inside of one Jinja tag into a Python statement, or None if it has no expression."""
    text = body.strip()
    if not is_block:
        return f"({text})" if text else None  # {{ expression }}
    keyword = text.split(None, 1)[0] if text else ""
    if keyword in ("if", "elif"):
        return f"({text[len(keyword) :].strip()})"
    if match := _FOR.match(text):  # {% for x in expression %}: only the iterable matters
        return f"({match.group(1).strip()})"
    if match := _SET.match(text):  # {% set name = expression %} types `name` like an assignment
        return f"{match.group(1)} = ({match.group(2).strip()})"
    return None  # endif, else, macro, include, ...


def _statements(text: str) -> tuple[list[tuple[int, str]], int]:
    """(line, python statement) for each expression, plus how many could not be parsed."""
    found: list[tuple[int, str]] = []
    unparsable = 0
    for m in _TAG.finditer(text):
        is_block = m.group(2) is not None
        body = m.group(2) if is_block else m.group(1)
        group = 2 if is_block else 1
        if body is None:  # a comment
            continue
        statement = _statement(_TILDE.sub(" + ", body), is_block)
        if statement is None:
            continue
        start = m.start(group) + len(body) - len(body.lstrip())
        try:
            ast.parse(statement)
        except SyntaxError:
            unparsable += 1  # e.g. `x is divisibleby 3`
            continue
        found.append((1 + text.count("\n", 0, start), statement))
    return found, unparsable


def _synthetic_source(statements: list[tuple[int, str]]) -> str:
    """Python source whose line numbers match the template's line numbers."""
    parts: list[str] = []
    current = 1
    for line, statement in sorted(statements):
        if line > current:
            parts.append("\n" * (line - current))
            current = line
        elif parts and not parts[-1].endswith("\n"):
            parts.append("; ")  # two expressions on one line
        parts.append(statement)
        current += statement.count("\n")
    return "".join(parts)


def jinja_refs(text: str, doctype: str) -> tuple[list[FieldRef], list[tuple[str, int]], int]:
    """Field refs, DocType-name refs and the count of unparsable expressions in a print format.

    In a print format `doc` is the document of `doctype` and `frappe` is available.
    """
    statements, unparsable = _statements(text)
    tree = ast.parse(_synthetic_source(statements))
    aliases = {"frappe": "frappe"}  # Jinja has `frappe` without importing it
    calls = [(n, resolve(n.func, aliases)) for n in ast.walk(tree) if isinstance(n, ast.Call)]
    field_refs, doctype_refs = collect_refs(tree, aliases, calls, seed={"doc": doctype})
    return field_refs, doctype_refs, unparsable
