"""Tests for Print Format scanning (Jinja templates and builder layouts)."""

import json
from pathlib import Path
from typing import Any

from tminus.engine.jinja_refs import jinja_refs
from tminus.engine.loader import load_rules
from tminus.engine.models import Finding
from tminus.engine.runner import scan_path

RULES = load_rules("v16")
ERP = "v16-erpnext-removed-or-renamed-fields"


def _print_format(tmp_path: Path, sibling_html: str | None, **extra: Any) -> Path:
    """Create a standard print format folder `pf` for Quotation and return the app root."""
    folder = tmp_path / "app" / "selling" / "print_format" / "pf"
    folder.mkdir(parents=True)
    document = {"doctype": "Print Format", "name": "PF", "doc_type": "Quotation"} | extra
    (folder / "pf.json").write_text(json.dumps(document, indent=1))
    if sibling_html is not None:
        (folder / "pf.html").write_text(sibling_html)
    return tmp_path


def _found(root: Path) -> list[Finding]:
    """The findings of the ERPNext field rule."""
    return [f for f in scan_path(root, RULES).findings if f.rule_id == ERP]


def test_html_file_expressions_are_checked(tmp_path: Path) -> None:
    """{{ doc.field }} in the .html file is checked against the print format's DocType."""
    root = _print_format(tmp_path, "<p>{{ doc.name }}</p>\n<p>{{ doc.source }}</p>\n")
    (found,) = _found(root)
    assert found.file.endswith("pf.html")
    assert found.line == 2
    assert 'print format "PF" for Quotation' in found.detail


def test_html_stored_in_the_json(tmp_path: Path) -> None:
    """A template stored in the JSON `html` key is reported on the key's line."""
    root = _print_format(tmp_path, None, html="<p>{{ doc.name }}</p>\n<p>{{ doc.source }}</p>")
    (found,) = _found(root)
    assert found.file.endswith("pf.json")
    assert "line 2 of the template" in found.detail


def test_statements_and_filters(tmp_path: Path) -> None:
    """if / for / set blocks, filters and the get() method are all read."""
    html = (
        "{% if doc.source %}a{% endif %}\n"
        "{% for x in doc.campaign %}{{ x }}{% endfor %}\n"
        '{{ doc.get("campaign") }}\n'
        '{{ doc.source|default("") }}\n'
        '{% set label = "x" ~ doc.campaign %}\n'
    )
    assert [f.line for f in _found(_print_format(tmp_path, html))] == [1, 2, 3, 4, 5]


def test_variable_typed_through_get_doc(tmp_path: Path) -> None:
    """{% set l = frappe.get_doc("Lead", ...) %} types `l` as a Lead."""
    html = '{% set l = frappe.get_doc("Lead", doc.party_name) %}\n{{ l.source }}\n'
    assert [f.line for f in _found(_print_format(tmp_path, html))] == [2]


def test_current_fields_are_clean(tmp_path: Path) -> None:
    """The new field name is not flagged."""
    assert _found(_print_format(tmp_path, "{{ doc.utm_source }}")) == []


def test_unparsable_expression_is_listed(tmp_path: Path) -> None:
    """An expression that is not valid Python-style syntax is reported as not checked."""
    root = _print_format(tmp_path, "{{ doc.qty is divisibleby 3 }}{{ doc.source }}")
    result = scan_path(root, RULES)
    assert any("1 Jinja expressions could not be parsed" in n for n in result.skipped)
    assert len([f for f in result.findings if f.rule_id == ERP]) == 1


def test_builder_layout_fields(tmp_path: Path) -> None:
    """Fields listed by the Print Format Builder are checked; child columns are not."""
    layout = [
        {"fieldname": "source", "fieldtype": "Data"},
        {
            "fieldname": "items",
            "fieldtype": "Table",
            "visible_columns": [{"fieldname": "campaign"}],
        },
    ]
    root = _print_format(tmp_path, None, format_data=json.dumps(layout))
    assert [f.detail.split(":")[0] for f in _found(root)] == ["Quotation.source"]


def test_builder_custom_html_block(tmp_path: Path) -> None:
    """Jinja inside a Custom HTML block of the builder layout is scanned."""
    layout = [{"fieldtype": "Custom HTML", "fieldname": "h", "options": "<b>{{ doc.source }}</b>"}]
    assert len(_found(_print_format(tmp_path, None, format_data=json.dumps(layout)))) == 1


def test_js_print_formats_are_skipped(tmp_path: Path) -> None:
    """Print formats of type JS are not Jinja and are left alone."""
    assert _found(_print_format(tmp_path, "{{ doc.source }}", print_format_type="JS")) == []


def test_ignore_comment_in_template(tmp_path: Path) -> None:
    """A {# tminus: ignore[...] #} comment on the same line suppresses the finding."""
    html = f"{{{{ doc.source }}}} {{# tminus: ignore[{ERP}] #}}\n"
    assert _found(_print_format(tmp_path, html)) == []


def test_jinja_line_numbers_and_two_expressions_on_a_line() -> None:
    """Template line numbers carry over to the references."""
    refs, _, bad = jinja_refs(
        "a\n{{ doc.source }} {{ doc.campaign }}\n\n{{ doc.source }}", "Quotation"
    )
    assert bad == 0
    assert sorted((r.name, r.line) for r in refs if r.doctype == "Quotation") == [
        ("campaign", 2),
        ("source", 2),
        ("source", 4),
    ]


def test_multiline_expression_keeps_later_line_numbers() -> None:
    """An expression that spans lines does not shift the lines of what follows."""
    text = '{{ frappe.db.get_value("Lead",\n  doc.party_name,\n  "source") }}\n{{ doc.campaign }}\n'
    refs, _, _ = jinja_refs(text, "Quotation")
    assert ("campaign", 4) in {(r.name, r.line) for r in refs}
