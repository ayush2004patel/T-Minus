import frappe.model.document
from frappe.desk.doctype.todo.todo import ToDo


class CustomToDo(ToDo):
    pass


class Mixin:
    pass


class CustomTask(Mixin, frappe.model.document.Document):
    pass