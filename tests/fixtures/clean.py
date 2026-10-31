# Code that must produce no findings.
import json
import importlib

try:
    import imp  # guarded: the except clause catches ImportError
except ImportError:
    imp = None

import cgi  # tminus: ignore[v16-removed-python-stdlib]


# --- call rules: correct v16 usage and guarded compat code
import erpnext.stock.get_item_details as gid
from erpnext.controllers import taxes_and_totals
from erpnext.accounts.party import validate_party_frozen_disabled

gid.get_item_tax_map(doc=doc, tax_template="GST 5%")  # keyword form is fine
taxes_and_totals.get_itemised_tax(doc)  # passing the document is fine
validate_party_frozen_disabled(company, "Customer", "CUST-0001")  # three arguments

try:
    from hrms.payroll.doctype.employee_benefit_application.employee_benefit_application import get_max_benefits
except ImportError:  # compat pattern: v16 no longer has it
    get_max_benefits = None