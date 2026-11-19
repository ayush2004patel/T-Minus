import frappe


def record(doc, method=None):
    frappe.logger().info(doc.name)