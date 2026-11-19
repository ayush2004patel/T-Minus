"""Tests for the get_all SQL-string, first-row, doc_events commit, get_doc and hook rules."""

from pathlib import Path

import pytest

from tminus.engine.loader import load_rules
from tminus.engine.models import Finding
from tminus.engine.runner import scan_path
from tminus.engine.scanners.python_ast import scan_source

RULES = load_rules("v16")
SQL = "v16-get-all-sql-strings"
FIRST = "v16-first-row-without-order-by"
COMMIT = "v16-db-commit-in-doc-events"
GET_DOC = "v16-get-doc-extra-keywords"
HOOKS = "v16-removed-hooks"


def _hits(source: str, rule_id: str) -> list[tuple[int, str]]:
    """Return (line, detail) pairs for one rule."""
    found = scan_source("import frappe\n" + source, "x.py", RULES)
    return [(f.line - 1, f.detail) for f in found if f.rule_id == rule_id]  # line 1 is the import


# ---- SQL written as strings -------------------------------------------------------------------
def test_sql_function_in_fields() -> None:
    """sum(...) as a string is rejected by v16."""
    hits = _hits('frappe.get_all("X", fields=["sum(qty) as total"])\n', SQL)
    assert [line for line, _ in hits] == [1]
    assert "SQL functions are not allowed as strings" in hits[0][1]


def test_comma_separated_string_is_split_like_frappe() -> None:
    """Only the function part of "name, sum(qty)" is reported."""
    hits = _hits('frappe.get_all("X", fields="name, sum(qty)")\n', SQL)
    assert len(hits) == 1
    assert 'fields "sum(qty)"' in hits[0][1]


def test_comma_inside_a_function_does_not_split() -> None:
    """ifnull(a, 0) as b is one field, so it gives one finding."""
    assert len(_hits('frappe.get_all("X", fields=["ifnull(a, 0) as b"])\n', SQL)) == 1


@pytest.mark.parametrize("field", ["distinct batch_no", "'Leave Application' as doctype"])
def test_invalid_field_format(field: str) -> None:
    """distinct and quoted literals are not plain field names."""
    hits = _hits(f'frappe.get_all("X", fields=["{field}"])\n', SQL)
    assert len(hits) == 1
    assert "Invalid field format" in hits[0][1]


@pytest.mark.parametrize(
    "field", ["name", "*", "`tabItem`.name", "item_code as code", "t.name as n", "`tabItem`.`name`"]
)
def test_accepted_field_formats(field: str) -> None:
    """Everything v16 accepts is left alone."""
    assert _hits(f'frappe.get_all("X", fields=["{field}"])\n', SQL) == []


def test_positional_fields_and_db_alias() -> None:
    """Fields given positionally, and via frappe.db.get_all, are checked."""
    assert len(_hits('frappe.get_all("X", ["sum(qty)"], {"a": 1})\n', SQL)) == 1
    assert len(_hits('frappe.db.get_all("X", fields=["sum(qty)"])\n', SQL)) == 1
    assert len(_hits('frappe.get_list("X", fields=["sum(qty)"])\n', SQL)) == 1


def test_function_in_filters() -> None:
    """SQL expressions as filter keys or as the field of a filter list are rejected."""
    assert len(_hits('frappe.get_all("X", filters={"ifnull(batch_no, \'\')": ""})\n', SQL)) == 1
    assert (
        len(_hits('frappe.get_all("X", filters=[["ifnull(batch_no, \'\')", "=", ""]])\n', SQL)) == 1
    )
    assert _hits('frappe.get_all("X", filters={"status": "Open"})\n', SQL) == []


def test_filter_triple_passed_as_fields_is_not_misread() -> None:
    """A flat ["status", "=", "Open"] passed positionally is a filter, not a field list."""
    assert _hits('frappe.get_all("X", ["status", "=", "Open"])\n', SQL) == []


def test_non_literal_and_other_apis_are_ignored() -> None:
    """Variables and frappe.db.sql are not analysed."""
    assert _hits('frappe.get_all("X", fields=fields)\n', SQL) == []
    assert _hits('frappe.db.sql("select sum(qty) from tabX")\n', SQL) == []


def test_sql_ignore_comment() -> None:
    """A tminus ignore comment suppresses the finding."""
    src = f'frappe.get_all("X", fields=["sum(qty)"])  # tminus: ignore[{SQL}]\n'
    assert _hits(src, SQL) == []


# ---- first row without order_by --------------------------------------------------------------
def test_first_and_last_row_directly() -> None:
    """[0] and [-1] on the call are flagged."""
    src = 'a = frappe.get_all("X")[0]\nb = frappe.get_list("X", filters={})[-1]\n'
    assert [line for line, _ in _hits(src, FIRST)] == [1, 2]


def test_limit_one_without_order_by() -> None:
    """limit_page_length=1 and limit=1 without an order are flagged."""
    src = 'frappe.get_all("X", limit_page_length=1)\nfrappe.get_all("X", limit=1)\n'
    assert [line for line, _ in _hits(src, FIRST)] == [1, 2]


def test_first_row_through_a_variable() -> None:
    """rows = get_all(...); rows[0] inside a function is flagged."""
    src = 'def f():\n    rows = frappe.get_all("X")\n    return rows[0]\n'
    assert [line for line, _ in _hits(src, FIRST)] == [3]


def test_ordered_queries_are_fine() -> None:
    """With an order_by nothing depends on the default order."""
    src = (
        'frappe.get_all("X", order_by="creation desc")[0]\n'
        'frappe.get_all("X", order_by="creation desc", limit_page_length=1)\n'
        'rows = frappe.get_all("X", order_by="name")\nrows[0]\n'
    )
    assert _hits(src, FIRST) == []


def test_other_indexes_and_limits_are_fine() -> None:
    """[1], a bigger limit and loops are not "first row" patterns."""
    src = (
        'frappe.get_all("X")[1]\n'
        'frappe.get_all("X", limit=20)\n'
        'for r in frappe.get_all("X"):\n'
        "    pass\n"
    )
    assert _hits(src, FIRST) == []


def test_existence_checks_are_not_first_row_use() -> None:
    """Calls that are only tested for emptiness do not depend on the order."""
    src = (
        'if not frappe.get_all("X", limit=1):\n    pass\n'
        'if frappe.get_all("X", limit_page_length=1):\n    pass\n'
        'if rows := frappe.get_all("X", limit=1):\n    pass\n'
    )
    assert _hits(src, FIRST) == []


def test_limit_one_used_as_data_is_still_flagged() -> None:
    """limit 1 whose rows are used is flagged even inside an if body."""
    src = 'if flag:\n    row = frappe.get_all("X", limit=1)\n'
    assert [line for line, _ in _hits(src, FIRST)] == [2]


def test_lookup_by_name_is_not_flagged() -> None:
    """A filter on `name` identifies one record, so the order cannot matter."""
    src = 'frappe.get_all("X", filters={"name": n})[0]\nfrappe.get_list("X", {"name": n})[0]\n'
    assert _hits(src, FIRST) == []


def test_kwargs_expansion_is_not_guessed() -> None:
    """If the call is built with **kwargs we do not know whether an order is given."""
    assert _hits('frappe.get_all("X", **opts)[0]\n', FIRST) == []


def test_reused_variable_is_not_guessed() -> None:
    """A variable assigned twice is ambiguous."""
    src = 'def f():\n    rows = frappe.get_all("X")\n    rows = other()\n    return rows[0]\n'
    assert _hits(src, FIRST) == []


# ---- get_doc keywords ------------------------------------------------------------------------
def test_get_doc_with_extra_keyword() -> None:
    """frappe.get_doc("X", name, status="Open") no longer applies the value."""
    assert len(_hits('frappe.get_doc("X", name, status="Open")\n', GET_DOC)) == 1


@pytest.mark.parametrize(
    "call",
    [
        'frappe.get_doc("X", name)',
        'frappe.get_doc("X", name, for_update=True)',
        'frappe.get_doc("X", name, check_permission=False)',
        'frappe.get_doc({"doctype": "X", "status": "Open"})',
        'frappe.get_doc("X", name, **kwargs)',
        'frappe.get_doc("X", status="Open")',
    ],
)
def test_get_doc_calls_that_are_fine(call: str) -> None:
    """Allowed keywords, the dict form, ** expansion and a single positional are not flagged."""
    assert _hits(call + "\n", GET_DOC) == []


# ---- doc_events commits and removed hooks ----------------------------------------------------
def _app(tmp_path: Path, hooks: str, events: str = "", app: str = "myapp") -> Path:
    """Create an app with hooks.py and events.py and return the root folder."""
    pkg = tmp_path / app
    pkg.mkdir()
    (pkg / "hooks.py").write_text(hooks)
    (pkg / "events.py").write_text(events)
    return tmp_path


def _found(root: Path, rule_id: str) -> list[Finding]:
    """Findings of one rule."""
    return [f for f in scan_path(root, RULES).findings if f.rule_id == rule_id]


def test_commit_in_doc_events_function(tmp_path: Path) -> None:
    """A frappe.db.commit() directly in a doc_events function is reported on its line."""
    hooks = 'doc_events = {"Sales Invoice": {"on_submit": "myapp.events.record"}}\n'
    events = "import frappe\n\n\ndef record(doc, method=None):\n    frappe.db.commit()\n"
    (found,) = _found(_app(tmp_path, hooks, events), COMMIT)
    assert found.file.endswith("events.py")
    assert found.line == 5
    assert 'doc_events["Sales Invoice"]["on_submit"]' in found.detail


def test_commit_through_an_alias(tmp_path: Path) -> None:
    """`from frappe import db` then db.commit() is recognised."""
    hooks = 'doc_events = {"X": {"validate": "myapp.events.f"}}\n'
    events = "from frappe import db\n\n\ndef f(doc, method=None):\n    db.commit()\n"
    assert len(_found(_app(tmp_path, hooks, events), COMMIT)) == 1


def test_commit_with_wildcard_and_tuple_keys_and_lists(tmp_path: Path) -> None:
    """ "*", a tuple of DocTypes and a list of functions are all covered."""
    hooks = (
        "doc_events = {\n"
        '    "*": {"on_update": "myapp.events.a"},\n'
        '    ("A", "B"): {"validate": ["myapp.events.b"]},\n'
        "}\n"
    )
    events = (
        "import frappe\n\n\ndef a(doc, method=None):\n    frappe.db.commit()\n\n\n"
        "def b(doc, method=None):\n    frappe.db.commit()\n"
    )
    assert len(_found(_app(tmp_path, hooks, events), COMMIT)) == 3  # a, and b for both DocTypes


def test_no_commit_and_commit_in_a_helper_are_not_reported(tmp_path: Path) -> None:
    """Only commits written in the hook function itself are found."""
    hooks = 'doc_events = {"X": {"validate": "myapp.events.f"}}\n'
    events = (
        "import frappe\n\n\ndef helper():\n    frappe.db.commit()\n\n\n"
        "def f(doc, method=None):\n    helper()\n"
    )
    assert _found(_app(tmp_path, hooks, events), COMMIT) == []


def test_commit_outside_hooks_is_fine(tmp_path: Path) -> None:
    """A commit in a function that is not a doc_events hook is not this rule's business."""
    hooks = 'doc_events = {"X": {"validate": "myapp.events.f"}}\n'
    events = (
        "import frappe\n\n\ndef f(doc, method=None):\n    pass\n\n\n"
        "def job():\n    frappe.db.commit()\n"
    )
    assert _found(_app(tmp_path, hooks, events), COMMIT) == []


def test_commit_ignore_comment(tmp_path: Path) -> None:
    """A tminus ignore comment on the commit line suppresses the finding."""
    hooks = 'doc_events = {"X": {"validate": "myapp.events.f"}}\n'
    events = (
        "import frappe\n\n\ndef f(doc, method=None):\n"
        f"    frappe.db.commit()  # tminus: ignore[{COMMIT}]\n"
    )
    assert _found(_app(tmp_path, hooks, events), COMMIT) == []


def test_removed_hooks_are_reported_with_a_note(tmp_path: Path) -> None:
    """leaderboards and advance_payment_doctypes are reported with what replaces them."""
    hooks = (
        'leaderboards = "myapp.lb.get"\n'
        'advance_payment_doctypes = ["Sales Order"]\n'
        'app_name = "x"\n'
    )
    found = _found(_app(tmp_path, hooks), HOOKS)
    assert [f.line for f in found] == [1, 2]
    assert "advance_payment_receivable_doctypes" in found[1].detail


def test_removed_hooks_are_not_reported_for_upstream_apps(tmp_path: Path) -> None:
    """frappe, erpnext and hrms still define them in their own version-15 hooks.py."""
    assert _found(_app(tmp_path, 'leaderboards = "x"\n', app="erpnext"), HOOKS) == []
