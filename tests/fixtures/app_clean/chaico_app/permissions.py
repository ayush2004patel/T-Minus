def customer_has_permission(doc, ptype, user):
    if doc.disabled:
        return False
    return True


def item_has_permission(doc, ptype, user):
    if doc.disabled:
        return False
    else:
        return True
