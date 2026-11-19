import frappe


def record(doc, method=None):
    frappe.db.commit()  # ignored in v16