# Deliberately bad code: every rule must flag at least one line here.
import imghdr
import cgi
from imp import reload
import distutils.core
import telnetlib
import frappe

from erpnext.stock.utils import get_batch_incoming_rate  # removed in v16
import erpnext.stock.get_item_details as gid
from erpnext.controllers import taxes_and_totals
from erpnext.accounts.party import validate_party_frozen_disabled
from hrms.payroll.doctype.employee_benefit_application.employee_benefit_application import get_max_benefits
from erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category import get_tax_withholding_details

gid.get_item_tax_map("Chai Co", "GST 5%")  # positional call: v16 is keyword-only
taxes_and_totals.get_itemised_tax(doc.taxes)  # v16 takes the document
validate_party_frozen_disabled("Customer", "CUST-0001")  # v16 needs company first

frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")  # moved to Company
frappe.get_all("Asset", fields=["name", "gross_purchase_amount"])  # renamed
asset = frappe.get_doc("Asset", "AST-0001")
asset.gross_purchase_amount = 10  # renamed
frappe.db.get_value("Communication", "COM-1", "rating")  # frappe field removed
frappe.db.get_value("Salary Slip", "SAL-1", "deduct_tax_for_unclaimed_employee_benefits")  # hrms
frappe.get_doc("Lead Source", "Website")  # DocType removed