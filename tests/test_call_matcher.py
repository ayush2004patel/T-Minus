"""Tests for the call matcher (removed functions and changed signatures)."""

from tminus.engine.loader import load_rules
from tminus.engine.scanners.python_ast import scan_source

RULES = load_rules("v16")
BATCH = "v16-erpnext-removed-get-batch-incoming-rate"
TAX_MAP = "v16-erpnext-get-item-tax-map-keyword-only"
ITEMISED = "v16-erpnext-get-itemised-tax-takes-doc"
FROZEN = "v16-erpnext-validate-party-frozen-disabled-company-arg"
MAX_BENEFITS = "v16-hrms-removed-get-max-benefits"
TDS = "v16-erpnext-removed-tax-withholding-helpers"

TAX_MAP_IMPORT = "import erpnext.stock.get_item_details as gid\n"
ITEMISED_IMPORT = "from erpnext.controllers.taxes_and_totals import get_itemised_tax\n"
FROZEN_IMPORT = "from erpnext.accounts.party import validate_party_frozen_disabled as v\n"


def _hits(source: str) -> list[tuple[str, int]]:
    """Return (rule id, line) pairs for the call-related rules only."""
    wanted = {BATCH, TAX_MAP, ITEMISED, FROZEN, MAX_BENEFITS, TDS}
    return [(f.rule_id, f.line) for f in scan_source(source, "x.py", RULES) if f.rule_id in wanted]


def test_removed_from_import() -> None:
    """Importing a removed function by name is flagged on the import line."""
    assert _hits("from erpnext.stock.utils import get_batch_incoming_rate\n") == [(BATCH, 1)]


def test_removed_in_second_module() -> None:
    """The same function in stock_ledger is covered too."""
    assert _hits("from erpnext.stock.stock_ledger import get_batch_incoming_rate\n") == [(BATCH, 1)]


def test_removed_through_module_alias() -> None:
    """`u.get_batch_incoming_rate(...)` is found through the import alias."""
    src = "import erpnext.stock.utils as u\nu.get_batch_incoming_rate(1)\n"
    assert _hits(src) == [(BATCH, 2)]


def test_removed_through_full_dotted_path() -> None:
    """A fully dotted call is found when the top package was imported."""
    src = "import erpnext\nerpnext.stock.utils.get_batch_incoming_rate(1)\n"
    assert _hits(src) == [(BATCH, 2)]


def test_other_function_from_same_module_is_fine() -> None:
    """Importing something else from the same module is not flagged."""
    assert _hits("from erpnext.stock.utils import get_stock_balance\n") == []


def test_guarded_import_is_skipped() -> None:
    """The try/except ImportError compat pattern is not flagged."""
    src = (
        "try:\n"
        "    from erpnext.stock.utils import get_batch_incoming_rate\n"
        "except ImportError:\n"
        "    get_batch_incoming_rate = None\n"
    )
    assert _hits(src) == []


def test_hrms_removed_helper() -> None:
    """The removed HRMS helper is flagged."""
    mod = "hrms.payroll.doctype.employee_benefit_application.employee_benefit_application"
    assert _hits(f"from {mod} import get_max_benefits\n") == [(MAX_BENEFITS, 1)]


def test_tax_withholding_helper_removed_but_kept_one_is_fine() -> None:
    """Removed helpers are flagged; get_tax_id_for_party still exists in v16."""
    mod = "erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category"
    assert _hits(f"from {mod} import get_tax_withholding_details\n") == [(TDS, 1)]
    assert _hits(f"from {mod} import get_tax_id_for_party\n") == []


def test_keyword_only_positional_call_flagged() -> None:
    """get_item_tax_map with positional arguments is flagged."""
    assert _hits(TAX_MAP_IMPORT + 'gid.get_item_tax_map("Co", "GST")\n') == [(TAX_MAP, 2)]


def test_keyword_only_keyword_call_is_fine() -> None:
    """get_item_tax_map called with keywords is fine."""
    assert _hits(TAX_MAP_IMPORT + 'gid.get_item_tax_map(doc=d, tax_template="GST")\n') == []


def test_itemised_tax_attribute_argument_flagged() -> None:
    """get_itemised_tax(doc.taxes) is flagged."""
    assert _hits(ITEMISED_IMPORT + "get_itemised_tax(doc.taxes)\n") == [(ITEMISED, 2)]


def test_itemised_tax_plain_name_argument_flagged() -> None:
    """get_itemised_tax(taxes) with a variable called taxes is flagged."""
    assert _hits(ITEMISED_IMPORT + "get_itemised_tax(taxes)\n") == [(ITEMISED, 2)]


def test_itemised_tax_old_keyword_flagged() -> None:
    """get_itemised_tax(taxes=...) uses the v15 parameter name."""
    assert _hits(ITEMISED_IMPORT + "get_itemised_tax(taxes=rows)\n") == [(ITEMISED, 2)]


def test_itemised_tax_document_argument_is_fine() -> None:
    """get_itemised_tax(doc) is the v16 form."""
    assert _hits(ITEMISED_IMPORT + "get_itemised_tax(doc)\n") == []


def test_positional_count_old_call_flagged_through_alias() -> None:
    """A two-argument call is flagged even when the function was imported with an alias."""
    assert _hits(FROZEN_IMPORT + 'v("Customer", name)\n') == [(FROZEN, 2)]


def test_positional_count_new_call_is_fine() -> None:
    """A three-argument call is the v16 form."""
    assert _hits(FROZEN_IMPORT + 'v(company, "Customer", name)\n') == []


def test_positional_count_ignores_starred_and_keyword_calls() -> None:
    """Calls we cannot count reliably are not flagged."""
    assert _hits(FROZEN_IMPORT + "v(*args)\n") == []
    assert _hits(FROZEN_IMPORT + "v(party_type=a, party_name=b)\n") == []


def test_unimported_name_with_same_function_name_is_ignored() -> None:
    """A local function that happens to share the name is not the ERPNext one."""
    assert _hits('def get_item_tax_map(a, b):\n    pass\nget_item_tax_map("x", "y")\n') == []


def test_ignore_comment() -> None:
    """A tminus ignore comment suppresses a call finding."""
    src = f"from erpnext.stock.utils import get_batch_incoming_rate  # tminus: ignore[{BATCH}]\n"
    assert _hits(src) == []
