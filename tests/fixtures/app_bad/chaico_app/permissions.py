def customer_has_permission(doc, ptype, user):
    if doc.disabled:
        return False


def item_has_permission(doc, ptype, user=None):
    if doc.disabled:
        return False
    return None


def supplier_has_permission(doc, ptype, user):
    if doc.disabled:
        return False
    elif ptype == "read":
        return True
