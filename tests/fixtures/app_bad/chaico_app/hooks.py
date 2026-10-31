app_name = "chaico_app"
has_permission = {
    "Customer": "chaico_app.permissions.customer_has_permission",  # falls off the end
    "Item": "chaico_app.permissions.item_has_permission",  # explicit return None
    "Supplier": "chaico_app.permissions.supplier_has_permission",  # branch without return
    "Lead": "erpnext.selling.lead_permission",  # outside this app: unreadable
    "Quotation": "chaico_app.permissions.missing_function",  # function does not exist
}
