"""Tests for field and DocType detection in client-side JavaScript."""

from tminus.engine.loader import load_rules
from tminus.engine.scanners.js_ast import scan_js

RULES = load_rules("v16")
ERP = "v16-erpnext-removed-or-renamed-fields"
NAMES = "v16-removed-doctypes"


def _hits(source: str, rule_id: str = ERP) -> list[tuple[int, str]]:
    """Return (line, detail) pairs for one rule."""
    findings, _ = scan_js(source.encode(), "x.js", RULES)
    return [(f.line, f.detail) for f in findings if f.rule_id == rule_id]


def _form(body: str, doctype: str = "Asset") -> str:
    """Wrap a handler body in frappe.ui.form.on(<doctype>, { refresh(frm) {...} })."""
    return f'frappe.ui.form.on("{doctype}", {{\n  refresh(frm) {{\n    {body}\n  }}\n}});\n'


def test_frm_doc_attribute() -> None:
    """frm.doc.field is checked against the DocType of the form script."""
    hits = _hits(_form("x = frm.doc.gross_purchase_amount;"))
    assert [line for line, _ in hits] == [3]
    assert hits[0][1].startswith("Asset.gross_purchase_amount: renamed to net_purchase_amount")


def test_frm_doc_subscript_and_cur_frm() -> None:
    """frm.doc["field"] and cur_frm.doc.field are checked too."""
    assert len(_hits(_form('x = frm.doc["gross_purchase_amount"];'))) == 1
    assert len(_hits(_form("x = cur_frm.doc.gross_purchase_amount;"))) == 1


def test_frm_methods_with_a_field_name() -> None:
    """The form methods that take a field name as their first argument are checked."""
    body = (
        'frm.set_value("gross_purchase_amount", 1);\n'
        'frm.toggle_display("gross_purchase_amount", true);\n'
        'frm.toggle_reqd("gross_purchase_amount", 1);\n'
        'frm.set_df_property("gross_purchase_amount", "hidden", 1);\n'
        'frm.get_field("gross_purchase_amount");\n'
        'frm.refresh_field("gross_purchase_amount");\n'
    )
    assert [line for line, _ in _hits(_form(body))] == [3, 4, 5, 6, 7, 8]


def test_frm_set_value_with_object_and_toggle_with_list() -> None:
    """Object keys and lists of field names are read."""
    assert len(_hits(_form("frm.set_value({gross_purchase_amount: 1, status: 'x'});"))) == 1
    assert len(_hits(_form('frm.toggle_display(["status", "gross_purchase_amount"], true);'))) == 1


def test_fields_dict_access() -> None:
    """frm.fields_dict.field and frm.fields_dict["field"] are checked."""
    assert len(_hits(_form("frm.fields_dict.gross_purchase_amount.df.hidden = 1;"))) == 1
    assert len(_hits(_form('frm.fields_dict["gross_purchase_amount"];'))) == 1


def test_set_df_property_for_a_child_table_field_is_skipped() -> None:
    """With a table_field argument the field belongs to the child table, not to this form."""
    body = 'frm.set_df_property("gross_purchase_amount", "hidden", 1, cdn, "items");'
    assert _hits(_form(body)) == []


def test_set_query_for_a_child_field_is_skipped() -> None:
    """frm.set_query("child_field", "table_field", fn) names a field of the child table."""
    assert _hits(_form('frm.set_query("gross_purchase_amount", "items", () => ({}));')) == []
    assert len(_hits(_form('frm.set_query("gross_purchase_amount", () => ({}));'))) == 1


def test_function_and_arrow_handlers() -> None:
    """Handlers written as function expressions and arrow functions are typed the same way."""
    src = (
        'frappe.ui.form.on("Asset", {\n'
        "  a: function (frm) { frm.doc.gross_purchase_amount; },\n"
        "  b: (frm) => { frm.doc.gross_purchase_amount; },\n"
        "  c: frm => frm.doc.gross_purchase_amount,\n"
        "});\n"
    )
    assert [line for line, _ in _hits(src)] == [2, 3, 4]


def test_field_trigger_handler_for_a_removed_field() -> None:
    """A handler named after a removed field never fires any more."""
    src = 'frappe.ui.form.on("Asset", {\n  gross_purchase_amount(frm) {},\n});\n'
    assert [line for line, _ in _hits(src)] == [2]


def test_legacy_three_argument_form_on() -> None:
    """frappe.ui.form.on("X", "field", fn) names the field and types the handler."""
    src = (
        'frappe.ui.form.on("Asset", "gross_purchase_amount", function (frm) {\n'
        "  frm.doc.is_existing_asset;\n"
        "});\n"
    )
    assert [line for line, _ in _hits(src)] == [1, 2]


def test_alias_of_frm_doc() -> None:
    """const doc = frm.doc; doc.field is checked."""
    assert len(_hits(_form("const doc = frm.doc; x = doc.gross_purchase_amount;"))) == 1


def test_other_doctype_is_not_flagged() -> None:
    """Issue.source is not a removed field."""
    assert _hits(_form("x = frm.doc.source;", "Issue")) == []


def test_current_field_name_is_fine() -> None:
    """The new name is clean."""
    assert _hits(_form("x = frm.doc.net_purchase_amount;")) == []


def test_child_row_event_types_the_row_not_frm() -> None:
    """In (frm, cdt, cdn) events the row is the child DocType and frm is an unknown parent."""
    src = (
        'frappe.ui.form.on("Purchase Order Item", {\n'
        "  qty(frm, cdt, cdn) {\n"
        "    const row = locals[cdt][cdn];\n"
        "    x = row.subcontracted_quantity;\n"
        "    y = frm.doc.apply_tds;\n"
        "  },\n"
        "});\n"
    )
    assert [line for line, _ in _hits(src)] == [4]


def test_child_row_event_with_frappe_model_and_get_doc() -> None:
    """frappe.model.get_value(cdt, cdn, "f") and frappe.get_doc(cdt, cdn) use the child type."""
    src = (
        'frappe.ui.form.on("Purchase Order Item", {\n'
        "  qty(frm, cdt, cdn) {\n"
        '    frappe.model.get_value(cdt, cdn, "subcontracted_quantity");\n'
        "    const d = frappe.get_doc(cdt, cdn);\n"
        "    d.subcontracted_quantity;\n"
        "  },\n"
        "});\n"
    )
    assert [line for line, _ in _hits(src)] == [3, 5]


def test_controller_this_frm_is_not_guessed() -> None:
    """this.frm.doc.field in a shared controller has no known DocType."""
    assert _hits("class C { f() { return this.frm.doc.gross_purchase_amount; } }\n") == []


def test_db_apis_with_a_literal_doctype() -> None:
    """frappe.db.get_value / set_value / get_single_value / get_list name the DocType."""
    src = (
        'frappe.db.get_value("Asset", name, "gross_purchase_amount");\n'
        'frappe.db.get_value("Asset", name, ["status", "gross_purchase_amount"]);\n'
        'frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto");\n'
        'frappe.db.set_value("Asset", name, "gross_purchase_amount", 1);\n'
        'frappe.db.get_list("Asset", { fields: ["gross_purchase_amount"],'
        " filters: { is_existing_asset: 1 } });\n"
        'frappe.ui.form.trigger("Asset", "is_existing_asset");\n'
    )
    assert [line for line, _ in _hits(src)] == [1, 2, 3, 4, 5, 5, 6]


def test_frappe_call_arguments_with_doctype_and_fieldname() -> None:
    """An object with doctype + fieldname (frappe.call args) is checked."""
    src = (
        'frappe.call({ method: "x", args: { doctype: "Asset",'
        ' fieldname: "gross_purchase_amount" } });\n'
    )
    assert len(_hits(src)) == 1


def test_removed_doctype_names() -> None:
    """Removed DocTypes in form.on, new_doc, set_route and Link field definitions are flagged."""
    src = (
        'frappe.ui.form.on("Lead Source", {});\n'
        'frappe.new_doc("Blog Post");\n'
        'frappe.set_route("List", "Newsletter");\n'
        'const f = { fieldtype: "Link", options: "Lead Source", fieldname: "x" };\n'
        'const label = "Lead Source";\n'
    )
    assert [line for line, _ in _hits(src, NAMES)] == [1, 2, 3, 4]


def test_list_view_settings() -> None:
    """add_fields and the doc argument of get_indicator are checked."""
    src = (
        'frappe.listview_settings["Quotation"] = {\n'
        '  add_fields: ["status", "source"],\n'
        "  get_indicator: function (doc) {\n"
        "    return doc.campaign;\n"
        "  },\n"
        "};\n"
    )
    assert [line for line, _ in _hits(src)] == [2, 4]


def test_ignore_comment() -> None:
    """A // tminus: ignore comment suppresses the finding."""
    src = _form(f"x = frm.doc.gross_purchase_amount; // tminus: ignore[{ERP}]")
    assert _hits(src) == []


def test_syntax_errors_do_not_crash() -> None:
    """A broken file is reported as having errors and is still scanned where possible."""
    findings, has_errors = scan_js(
        b'frappe.db.get_value("Asset", n, "gross_purchase_amount"); }}}', "x.js", RULES
    )
    assert has_errors
    assert any(f.rule_id == ERP for f in findings)
