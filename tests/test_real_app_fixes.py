"""Fixes found by scanning a real app: quiet parsing, one report per query, inline `if`."""

import warnings

from tminus.engine.jinja_refs import jinja_refs
from tminus.engine.loader import load_rules
from tminus.engine.scanners.python_ast import scan_source

RULES = load_rules("v16")
FIRST = "v16-first-row-without-order-by"


def test_invalid_escape_in_scanned_code_prints_no_warning() -> None:
    """A JS regex inside a Python string must not make T-MINUS print a SyntaxWarning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        scan_source('x = "(is\\s)"\n', "x.py", RULES)
    assert caught == []


def test_jinja_inline_if_without_else() -> None:
    """{{ a if b }} is valid Jinja; its field uses are still found and nothing is "unparsable"."""
    refs, _, unparsable = jinja_refs(
        "{{ doc.source if doc.status }}\n{% set a = doc.campaign if doc.x %}", "Quotation"
    )
    assert unparsable == 0
    assert {r.name for r in refs if r.doctype == "Quotation"} >= {"source", "campaign", "status"}


def test_limit_one_and_first_row_are_reported_once() -> None:
    """rows = get_all(..., limit=1) then rows[0] is one finding, on the query."""
    src = (
        "import frappe\n\n\ndef f():\n"
        '    rows = frappe.get_all("Dynamic Link", limit_page_length=1)\n'
        "    return rows[0]\n"
    )
    lines = [f.line for f in scan_source(src, "x.py", RULES) if f.rule_id == FIRST]
    assert lines == [5]
