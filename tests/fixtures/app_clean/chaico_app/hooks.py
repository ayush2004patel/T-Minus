app_name = "chaico_app"
has_permission = {
    "Customer": "chaico_app.permissions.customer_has_permission",
    "Item": ["chaico_app.permissions.item_has_permission"],
}
