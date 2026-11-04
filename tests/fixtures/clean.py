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

# --- field and DocType rules: current names, other DocTypes, plain strings
import frappe

frappe.db.get_single_value("Company", "accounts_frozen_till_date")  # new location
frappe.get_all("Asset", fields=["name", "net_purchase_amount"])  # new name
invoice = frappe.get_doc("Sales Invoice", "SINV-1")
invoice.utm_source = "Website"  # new field
frappe.db.get_value("Issue", "ISS-1", "source")  # same field name on a DocType where it still exists
label = "Lead Source"  # a plain string is not passed to a Frappe API

# --- SQL text and query builder: current columns, other tables, quoted values
query_ok = """
    SELECT q.name, q.utm_source FROM `tabQuotation` q WHERE q.docstatus = 1
"""
issue_query = "SELECT i.source FROM `tabIssue` i WHERE i.status = 'source'"  # Issue.source exists