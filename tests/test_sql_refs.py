"""Tests for field detection inside SQL text and query-builder variables."""

from tminus.engine.loader import load_rules
from tminus.engine.scanners.python_ast import scan_source

RULES = load_rules("v16")
ERP = "v16-erpnext-removed-or-renamed-fields"


def _hits(source: str) -> list[tuple[int, str]]:
    """Return (line, detail) pairs for the ERPNext field rule."""
    found = scan_source(source, "x.py", RULES)
    return [(f.line, f.detail) for f in found if f.rule_id == ERP]


def test_qualified_column_through_alias() -> None:
    """alias.field is resolved through the table alias."""
    hits = _hits('q = "SELECT q.source FROM `tabQuotation` q"\n')
    assert len(hits) == 1
    assert hits[0][1].startswith("Quotation.source:")
    assert "SQL text" in hits[0][1]


def test_alias_with_as_keyword() -> None:
    """`tabX` AS alias also works."""
    assert len(_hits('q = "SELECT q.source FROM `tabQuotation` AS q"\n')) == 1


def test_single_table_bare_column() -> None:
    """With one table, a bare column name belongs to that table."""
    assert len(_hits('q = "SELECT name, source FROM tabLead WHERE status = 1"\n')) == 1


def test_multi_table_bare_column_is_not_guessed() -> None:
    """With two tables a bare column is ambiguous, so only qualified columns count."""
    src = 'q = "SELECT source FROM tabLead l JOIN tabQuotation x ON x.party_name = l.name"\n'
    assert _hits(src) == []
    qualified = (
        'q = "SELECT x.source FROM tabLead l JOIN tabQuotation x ON x.party_name = l.name"\n'
    )
    assert [d.split(":")[0] for _, d in _hits(qualified)] == ["Quotation.source"]


def test_same_column_on_a_table_where_it_exists_is_fine() -> None:
    """Issue.source is not in the removed table."""
    assert _hits('q = "SELECT i.source FROM `tabIssue` i"\n') == []


def test_column_qualified_by_full_table_name() -> None:
    """`tabX`.field is recognised without an alias."""
    src = 'q = "SELECT `tabSales Invoice`.campaign FROM `tabSales Invoice`"\n'
    assert len(_hits(src)) == 1


def test_plain_table_name_as_qualifier() -> None:
    """tabLead.source works for tables written without backticks."""
    assert len(_hits('q = "SELECT tabLead.source FROM tabLead"\n')) == 1


def test_line_number_inside_triple_quoted_query() -> None:
    """The finding points at the physical line of the column."""
    src = 'q = """\nSELECT name\nFROM `tabQuotation` q\nWHERE q.source = 1\n"""\n'
    assert [line for line, _ in _hits(src)] == [4]


def test_f_string_query() -> None:
    """Placeholders in an f-string do not break the parsing."""
    src = 'q = f"SELECT q.source FROM `tabQuotation` q WHERE q.company = {c}"\n'
    assert len(_hits(src)) == 1


def test_query_split_with_plus() -> None:
    """A query built as "..." + "..." is read as one text."""
    src = 'q = "SELECT q.source " + "FROM `tabQuotation` q"\n'
    assert len(_hits(src)) == 1


def test_quoted_value_is_not_a_column() -> None:
    """A quoted 'source' is a value, not a column."""
    assert _hits("q = \"SELECT name FROM tabLead WHERE status = 'source'\"\n") == []


def test_as_alias_is_not_a_column() -> None:
    """`AS source` introduces an alias, not the removed column."""
    assert _hits('q = "SELECT utm_source AS source FROM tabLead"\n') == []


def test_plain_text_without_a_table_is_ignored() -> None:
    """A sentence that mentions the word is not SQL."""
    assert _hits('msg = "source of the quotation"\n') == []


def test_query_builder_variable() -> None:
    """frappe.qb.DocType("X") variables are typed, so q.field is checked."""
    src = 'import frappe\nq = frappe.qb.DocType("Quotation")\nx = q.source\n'
    hits = _hits(src)
    assert [line for line, _ in hits] == [3]
    assert "SQL text" not in hits[0][1]


def test_query_builder_variable_with_alias_call() -> None:
    """frappe.qb.DocType("X").as_("q") is typed too."""
    src = 'import frappe\nq = frappe.qb.DocType("Quotation").as_("q")\nx = q.source\n'
    assert len(_hits(src)) == 1


def test_ignore_comment_on_sql_line() -> None:
    """A tminus ignore comment suppresses an SQL finding."""
    src = f'q = "SELECT q.source FROM `tabQuotation` q"  # tminus: ignore[{ERP}]\n'
    assert _hits(src) == []
