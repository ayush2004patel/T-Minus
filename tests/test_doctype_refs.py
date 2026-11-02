"""Tests for removed/renamed field and removed DocType detection."""

from tminus.engine.loader import load_rules
from tminus.engine.scanners.python_ast import scan_source

RULES = load_rules("v16")
ERP = "v16-erpnext-removed-or-renamed-fields"
FRAPPE = "v16-frappe-removed-fields"
HRMS = "v16-hrms-removed-fields"
NAMES = "v16-removed-doctypes"
IMPORT = "import frappe\n"


def _hits(source: str, rule_id: str = ERP) -> list[tuple[int, str]]:
    """Return (line, detail) pairs for one rule."""
    found = scan_source(IMPORT + source, "x.py", RULES)
    return [(f.line - 1, f.detail) for f in found if f.rule_id == rule_id]  # line 1 is the import


def test_single_value_removed_field() -> None:
    """get_single_value on a removed field reports where the field moved."""
    hits = _hits('frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")\n')
    assert hits == [
        (1, "Accounts Settings.acc_frozen_upto: moved to Company.accounts_frozen_till_date")
    ]


def test_get_all_fields_and_filters_and_order_by() -> None:
    """Fields, filter keys and order_by of get_all are all checked."""
    src = (
        'frappe.get_all("Asset", fields=["name", "gross_purchase_amount"])\n'
        'frappe.get_all("Asset", filters={"is_existing_asset": 1})\n'
        'frappe.get_all("Asset", order_by="gross_purchase_amount desc")\n'
    )
    assert [line for line, _ in _hits(src)] == [1, 2, 3]


def test_get_all_positional_filters_and_fields_in_either_order() -> None:
    """frappe.get_all accepts (doctype, filters, fields) and (doctype, fields, filters)."""
    src = (
        'frappe.get_all("Asset", {"is_existing_asset": 1}, ["name"])\n'
        'frappe.get_all("Asset", ["gross_purchase_amount"], {"status": "Draft"})\n'
    )
    assert [line for line, _ in _hits(src)] == [1, 2]


def test_filter_triples() -> None:
    """Filters written as [field, op, value] lists are checked."""
    src = 'frappe.get_all("Asset", filters=[["gross_purchase_amount", ">", 0]])\n'
    assert len(_hits(src)) == 1


def test_get_value_with_list_of_fields() -> None:
    """get_value with a list of fields flags only the removed one."""
    src = 'frappe.db.get_value("Asset", "A-1", ["name", "gross_purchase_amount"])\n'
    assert [d for _, d in _hits(src)] == [
        "Asset.gross_purchase_amount: renamed to net_purchase_amount"
    ]


def test_set_value_dict() -> None:
    """set_value with a dict of values checks its keys."""
    src = 'frappe.db.set_value("Asset", "A-1", {"gross_purchase_amount": 5})\n'
    assert len(_hits(src)) == 1


def test_same_field_name_on_another_doctype_is_fine() -> None:
    """Lead.source was removed, Issue.source is not in the table."""
    assert _hits('frappe.db.get_value("Issue", "I-1", "source")\n') == []


def test_current_field_name_is_fine() -> None:
    """The new name is not flagged."""
    assert _hits('frappe.get_all("Asset", fields=["net_purchase_amount"])\n') == []


def test_typed_variable_attribute() -> None:
    """Attribute access on a variable assigned from get_doc("Asset") is checked."""
    src = 'a = frappe.get_doc("Asset", "A-1")\nx = a.gross_purchase_amount\n'
    assert [line for line, _ in _hits(src)] == [2]


def test_typed_variable_get_set_and_subscript() -> None:
    """doc.get("f"), doc.set("f", v) and doc["f"] are checked."""
    src = (
        'a = frappe.get_doc("Asset", "A-1")\n'
        'a.get("gross_purchase_amount")\n'
        'a.set("gross_purchase_amount", 1)\n'
        'a["gross_purchase_amount"]\n'
    )
    assert [line for line, _ in _hits(src)] == [2, 3, 4]


def test_direct_call_attribute() -> None:
    """frappe.get_cached_doc("Accounts Settings").acc_frozen_upto is checked."""
    src = 'x = frappe.get_cached_doc("Accounts Settings").acc_frozen_upto\n'
    assert len(_hits(src)) == 1


def test_untyped_parameter_is_not_guessed() -> None:
    """A parameter called `a` is not assumed to be an Asset."""
    src = 'a = frappe.get_doc("Asset", "A-1")\ndef f(a):\n    return a.gross_purchase_amount\n'
    assert _hits(src) == []


def test_variable_assigned_two_doctypes_is_not_guessed() -> None:
    """A variable that holds two different DocTypes is ambiguous and skipped."""
    src = (
        'd = frappe.get_doc("Asset", "A-1")\n'
        'd = frappe.get_doc("Sales Invoice", "S-1")\n'
        "d.gross_purchase_amount\n"
    )
    assert _hits(src) == []


def test_variable_also_assigned_from_unknown_is_not_guessed() -> None:
    """A variable that is also assigned from something untyped is skipped."""
    src = 'd = frappe.get_doc("Asset", "A-1")\nd = other()\nd.gross_purchase_amount\n'
    assert _hits(src) == []


def test_dict_literal_with_doctype_key() -> None:
    """A dict describing a new document is checked."""
    src = 'frappe.get_doc({"doctype": "Asset", "gross_purchase_amount": 5}).insert()\n'
    assert len(_hits(src)) == 1


def test_utm_replacement_note_mentions_copying() -> None:
    """The note for source/campaign warns that old values are not copied."""
    hits = _hits('frappe.get_all("Quotation", fields=["source"])\n')
    assert "copy existing data yourself" in hits[0][1]


def test_frappe_and_hrms_rules() -> None:
    """Frappe and HRMS field removals are reported by their own rules."""
    assert len(_hits('frappe.db.get_value("Communication", "C-1", "rating")\n', FRAPPE)) == 1
    hrms = (
        'frappe.db.get_value("Salary Slip", "S-1", "deduct_tax_for_unclaimed_employee_benefits")\n'
    )
    assert len(_hits(hrms, HRMS)) == 1


def test_removed_doctype_in_api_call() -> None:
    """A removed DocType passed to an API is reported with its replacement."""
    hits = _hits('frappe.get_doc("Lead Source", "Web")\n', NAMES)
    assert hits == [(1, "Lead Source: replaced by UTM Source")]


def test_removed_doctype_in_qb_and_dict() -> None:
    """frappe.qb.DocType("X") and {"doctype": "X"} are checked."""
    assert len(_hits('t = frappe.qb.DocType("Blog Post")\n', NAMES)) == 1
    assert len(_hits('d = {"doctype": "Newsletter", "subject": "x"}\n', NAMES)) == 1


def test_removed_doctype_plain_string_is_fine() -> None:
    """A string that is not passed to a DocType API is not flagged."""
    assert _hits('label = "Lead Source"\n', NAMES) == []


def test_moved_doctypes_are_not_listed() -> None:
    """SMS Log and Print Heading still exist in v16 (they moved between apps)."""
    assert _hits('frappe.get_all("SMS Log")\nfrappe.get_all("Print Heading")\n', NAMES) == []


def test_ignore_comment() -> None:
    """A tminus ignore comment suppresses the finding."""
    src = f'frappe.get_doc("Lead Source", "Web")  # tminus: ignore[{NAMES}]\n'
    assert _hits(src, NAMES) == []
