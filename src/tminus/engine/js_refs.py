"""Find DocType fields and DocType names used in client-side JavaScript (via tree-sitter)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

import tree_sitter_javascript as tsjs
from tree_sitter import Language, Node, Parser

from tminus.engine.frappe_refs import FieldRef

_PARSER = Parser(Language(tsjs.language()))
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_FUNCTIONS = {"function_expression", "function", "arrow_function", "method_definition"}
_LINK_TYPES = {"Link", "Table", "Table MultiSelect"}

# frm.<method>(field, ...): the first argument names a field (or a list of fields).
FRM_FIELD_METHODS = {
    "set_value", "toggle_display", "toggle_reqd", "toggle_enable", "set_df_property", "get_field",
    "set_query", "refresh_field", "get_docfield", "add_child", "clear_table", "trigger",
    "set_currency_labels",
}  # fmt: skip


@dataclass(frozen=True)
class JsSlots:
    """Where a frappe JS API keeps field names (argument positions)."""

    filters: int | None = None  # filters object or [[field, op, value]] list
    fields: int | None = None  # field name, list of names, or object whose keys are names
    options: int | None = None  # options object with fields / filters / order_by


JS_APIS: dict[str, JsSlots] = {
    "frappe.db.get_value": JsSlots(filters=1, fields=2),
    "frappe.db.get_single_value": JsSlots(fields=1),
    "frappe.db.set_value": JsSlots(fields=2),
    "frappe.db.get_list": JsSlots(options=1),
    "frappe.model.get_value": JsSlots(filters=1, fields=2),
    "frappe.model.set_value": JsSlots(fields=2),
    "frappe.ui.form.trigger": JsSlots(fields=1),
}
DOCTYPE_APIS = set(JS_APIS) | {
    "frappe.get_doc",
    "frappe.new_doc",
    "frappe.db.get_doc",
    "frappe.get_meta",
    "frappe.model.with_doctype",
    "frappe.model.with_doc",
    "frappe.ui.form.on",
}


@dataclass
class _Env:
    """What is known about the variables inside one handler function."""

    frm_name: str = "frm"
    frm: str | None = None  # DocType of the form object, if the handler is a parent-form event
    cd: tuple[str, str, str] | None = None  # (cdt name, cdn name, child DocType) of row events
    docs: dict[str, str] = field(default_factory=dict)  # variable -> DocType of a document


def _walk(root: Node) -> Iterator[Node]:
    """Every node below (and including) root, parents before children."""
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


class _Scan:
    """Collects references from one parsed file."""

    def __init__(self, source: bytes) -> None:
        """Remember the source bytes and start with empty results."""
        self.src = source
        self.fields: list[FieldRef] = []
        self.doctypes: list[tuple[str, int]] = []

    # ---- small helpers -------------------------------------------------------------------
    def text(self, node: Node) -> str:
        """The source text of a node."""
        return self.src[node.start_byte : node.end_byte].decode("utf-8", "replace")

    def string(self, node: Node | None) -> str | None:
        """The value of a plain string literal (no substitutions), else None."""
        if node is None:
            return None
        if node.type == "string" or (
            node.type == "template_string"
            and not any(c.type == "template_substitution" for c in node.children)
        ):
            return self.text(node)[1:-1]
        return None

    def dotted(self, node: Node | None) -> str | None:
        """`a.b.c` for a chain of identifiers and property accesses, else None."""
        if node is None:
            return None
        if node.type == "identifier":
            return self.text(node)
        if node.type == "member_expression":
            base = self.dotted(node.child_by_field_name("object"))
            prop = node.child_by_field_name("property")
            return f"{base}.{self.text(prop)}" if base and prop else None
        return None

    def args(self, call: Node) -> list[Node]:
        """The arguments of a call (comments removed)."""
        arguments = call.child_by_field_name("arguments")
        return [c for c in arguments.named_children if c.type != "comment"] if arguments else []

    def key_name(self, node: Node | None) -> str | None:
        """The name of an object key (identifier or string)."""
        if node is None:
            return None
        if node.type in ("property_identifier", "identifier"):
            return self.text(node)
        return self.string(node)

    def params(self, fn: Node) -> list[str]:
        """Parameter names of a function node (plain identifiers only)."""
        single = fn.child_by_field_name("parameter")  # arrow function: x => ...
        if single is not None and single.type == "identifier":
            return [self.text(single)]
        formal = fn.child_by_field_name("parameters")
        if formal is None:
            return []
        return [self.text(c) for c in formal.named_children if c.type == "identifier"]

    def add(self, doctype: str, name: str, node: Node) -> None:
        """Record that `doctype.name` is used at this node's line."""
        self.fields.append(FieldRef(doctype, name, node.start_point[0] + 1))

    def names(self, node: Node | None, doctype: str, as_filters: bool = False) -> None:
        """Record field names in a string, a list of strings/filter triples, or object keys."""
        if node is None:
            return
        text = self.string(node)
        if text is not None:
            if not as_filters:
                for token in _TOKEN.findall(text):
                    self.add(doctype, token, node)
        elif node.type == "array":
            for item in node.named_children:
                inner = self.string(item)
                if inner is not None and not as_filters:
                    for token in _TOKEN.findall(inner):
                        self.add(doctype, token, item)
                elif item.type == "array" and len(item.named_children) in (3, 4):
                    pos = 1 if len(item.named_children) == 4 else 0  # [doctype, field, op, value]
                    field_name = self.string(item.named_children[pos])
                    if field_name is not None:
                        self.add(doctype, field_name, item)
        elif node.type == "object":
            for prop in node.named_children:
                if prop.type == "pair":
                    key = self.key_name(prop.child_by_field_name("key"))
                    if key:
                        self.add(doctype, key, prop)

    def options_object(self, node: Node | None, doctype: str) -> None:
        """Record fields named in a {fields, filters, order_by, ...} options object."""
        if node is None or node.type != "object":
            return
        for prop in node.named_children:
            if prop.type != "pair":
                continue
            key = self.key_name(prop.child_by_field_name("key"))
            value = prop.child_by_field_name("value")
            if key in ("fields", "fieldname", "order_by", "group_by"):
                self.names(value, doctype)
            elif key in ("filters", "or_filters"):
                self.names(value, doctype, as_filters=True)

    # ---- environment-independent references ------------------------------------------------
    def general(self, root: Node) -> None:
        """References that do not depend on a handler's variables (API calls, object literals)."""
        for node in _walk(root):
            if node.type == "call_expression":
                self.api_call(node)
            elif node.type == "object":
                self.object_literal(node)

    def api_call(self, call: Node) -> None:
        """frappe.db.get_value("X", ...) and friends: record the DocType and its fields."""
        path = self.dotted(call.child_by_field_name("function"))
        arguments = self.args(call)
        if path == "frappe.set_route" and len(arguments) >= 2:
            if self.string(arguments[0]) in ("List", "Form", "Report"):
                name = self.string(arguments[1])
                if name:
                    self.doctypes.append((name, call.start_point[0] + 1))
            return
        if path not in DOCTYPE_APIS or not arguments:
            return
        doctype = self.string(arguments[0])
        if doctype is None:
            return
        self.doctypes.append((doctype, call.start_point[0] + 1))
        slots = JS_APIS.get(path or "")
        if slots is None:
            return

        def at(pos: int | None) -> Node | None:
            """The argument at a position, if the call has one."""
            return arguments[pos] if pos is not None and pos < len(arguments) else None

        self.names(at(slots.filters), doctype, as_filters=True)
        self.names(at(slots.fields), doctype)
        self.options_object(at(slots.options), doctype)

    def object_literal(self, obj: Node) -> None:
        """{doctype: "X", fieldname/fields/filters: ...} and Link/Table field definitions."""
        props: dict[str, Node | None] = {}
        for prop in obj.named_children:
            if prop.type == "pair":
                key = self.key_name(prop.child_by_field_name("key"))
                if key:
                    props[key] = prop.child_by_field_name("value")
        line = obj.start_point[0] + 1
        doctype = self.string(props.get("doctype"))
        if doctype:
            self.doctypes.append((doctype, line))
            self.options_object(obj, doctype)
        options = self.string(props.get("options"))
        if options and self.string(props.get("fieldtype")) in _LINK_TYPES:
            self.doctypes.append((options, line))

    # ---- form scripts and list view settings -----------------------------------------------
    def forms_and_lists(self, root: Node) -> None:
        """frappe.ui.form.on(...) handlers and frappe.listview_settings[...] objects."""
        for node in _walk(root):
            if node.type == "call_expression":
                if self.dotted(node.child_by_field_name("function")) == "frappe.ui.form.on":
                    self.form_on(node)
            elif node.type == "assignment_expression":
                self.list_settings(node)

    def form_on(self, call: Node) -> None:
        """frappe.ui.form.on("X", {...}) or the legacy ("X", "field", fn) form."""
        arguments = self.args(call)
        doctype = self.string(arguments[0]) if arguments else None
        if doctype is None or len(arguments) < 2:
            return
        second = arguments[1]
        if second.type == "object":
            for prop in second.named_children:
                if prop.type == "pair":
                    name = self.key_name(prop.child_by_field_name("key"))
                    value = prop.child_by_field_name("value")
                elif prop.type == "method_definition":
                    name = self.key_name(prop.child_by_field_name("name"))
                    value = prop
                else:
                    continue
                if name:  # a handler named after a field is that field's change trigger
                    self.add(doctype, name, prop)
                if value is not None and value.type in _FUNCTIONS:
                    self.handler(value, doctype)
        else:
            name = self.string(second)
            if name:
                self.add(doctype, name, second)
            if len(arguments) >= 3 and arguments[2].type in _FUNCTIONS:
                self.handler(arguments[2], doctype)

    def list_settings(self, assign: Node) -> None:
        """frappe.listview_settings["X"] = { add_fields: [...], get_indicator(doc) {...} }."""
        left = assign.child_by_field_name("left")
        right = assign.child_by_field_name("right")
        if left is None or right is None or right.type != "object":
            return
        if left.type != "subscript_expression":
            return
        if self.dotted(left.child_by_field_name("object")) != "frappe.listview_settings":
            return
        doctype = self.string(left.child_by_field_name("index"))
        if doctype is None:
            return
        self.doctypes.append((doctype, assign.start_point[0] + 1))
        for prop in right.named_children:
            if prop.type == "pair":
                name = self.key_name(prop.child_by_field_name("key"))
                value = prop.child_by_field_name("value")
            elif prop.type == "method_definition":
                name = self.key_name(prop.child_by_field_name("name"))
                value = prop
            else:
                continue
            if name == "add_fields":
                self.names(value, doctype)
            elif name == "get_indicator" and value is not None and value.type in _FUNCTIONS:
                params = self.params(value)
                if params:
                    self.body_refs(value, _Env(docs={params[0]: doctype}))

    def handler(self, fn: Node, doctype: str) -> None:
        """Check one form-event handler: (frm) for the form itself, (frm, cdt, cdn) for rows."""
        params = self.params(fn)
        if len(params) >= 3:  # a child-table row event: `frm` is the parent form (unknown type)
            env = _Env(frm_name=params[0], cd=(params[1], params[2], doctype))
        else:
            env = _Env(frm_name=params[0] if params else "frm", frm=doctype)
        self.body_refs(fn, env)

    # ---- typed expressions inside a handler --------------------------------------------------
    def typed(self, node: Node | None, env: _Env) -> tuple[str, str] | None:
        """("frm" | "doc", DocType) if the expression is the form or a document of known type."""
        if node is None:
            return None
        if node.type == "identifier":
            name = self.text(node)
            if env.frm and name in (env.frm_name, "cur_frm"):
                return ("frm", env.frm)
            if name in env.docs:
                return ("doc", env.docs[name])
        elif node.type == "member_expression":
            obj = self.typed(node.child_by_field_name("object"), env)
            prop = node.child_by_field_name("property")
            if obj and obj[0] == "frm" and prop is not None and self.text(prop) == "doc":
                return ("doc", obj[1])  # frm.doc
        elif node.type == "subscript_expression" and env.cd:  # locals[cdt][cdn]
            outer_obj = node.child_by_field_name("object")
            inner = (
                outer_obj
                if outer_obj is not None and outer_obj.type == "subscript_expression"
                else None
            )
            if inner is not None and self.matches_locals(node, inner, env.cd):
                return ("doc", env.cd[2])
        elif node.type == "call_expression" and env.cd:  # frappe.get_doc(cdt, cdn)
            if self.dotted(node.child_by_field_name("function")) == "frappe.get_doc":
                arguments = [self.text(a) for a in self.args(node)]
                if arguments[:2] == [env.cd[0], env.cd[1]]:
                    return ("doc", env.cd[2])
        return None

    def matches_locals(self, outer: Node, inner: Node, cd: tuple[str, str, str]) -> bool:
        """True for `locals[<cdt>][<cdn>]` using this handler's row parameters."""
        base = inner.child_by_field_name("object")
        first = inner.child_by_field_name("index")
        second = outer.child_by_field_name("index")
        return (
            base is not None
            and self.text(base) == "locals"
            and first is not None
            and self.text(first) == cd[0]
            and second is not None
            and self.text(second) == cd[1]
        )

    def collect_docs(self, fn: Node, env: _Env) -> None:
        """Find `var row = locals[cdt][cdn]` / `const d = frm.doc` and remember their types."""
        conflicts: set[str] = set()
        for _ in range(2):  # twice, so a variable can be typed from an earlier typed variable
            for node in _walk(fn):
                name_node = value = None
                if node.type == "variable_declarator":
                    name_node = node.child_by_field_name("name")
                    value = node.child_by_field_name("value")
                elif node.type == "assignment_expression":
                    name_node = node.child_by_field_name("left")
                    value = node.child_by_field_name("right")
                if name_node is None or name_node.type != "identifier" or value is None:
                    continue
                name = self.text(name_node)
                result = self.typed(value, env)
                if result is None:
                    if name in env.docs:  # reassigned from something untyped
                        conflicts.add(name)
                elif result[0] == "doc":
                    if name in env.docs and env.docs[name] != result[1]:
                        conflicts.add(name)
                    env.docs[name] = result[1]
        for name in conflicts:
            env.docs.pop(name, None)

    def body_refs(self, fn: Node, env: _Env) -> None:
        """Record field uses through the form (frm), documents and rows inside a handler."""
        self.collect_docs(fn, env)
        for node in _walk(fn):
            if node.type == "member_expression":
                self.member_ref(node, env)
            elif node.type == "subscript_expression":
                self.subscript_ref(node, env)
            elif node.type == "call_expression":
                self.call_ref(node, env)

    def member_ref(self, node: Node, env: _Env) -> None:
        """doc.field, frm.doc.field and frm.fields_dict.field."""
        prop = node.child_by_field_name("property")
        obj = node.child_by_field_name("object")
        if prop is None or obj is None or prop.type != "property_identifier":
            return
        owner = self.typed(obj, env)
        if owner and owner[0] == "doc":
            self.add(owner[1], self.text(prop), node)
        elif obj.type == "member_expression":  # frm.fields_dict.field
            inner = obj.child_by_field_name("property")
            frm = self.typed(obj.child_by_field_name("object"), env)
            if frm and frm[0] == "frm" and inner is not None and self.text(inner) == "fields_dict":
                self.add(frm[1], self.text(prop), node)

    def subscript_ref(self, node: Node, env: _Env) -> None:
        """doc["field"] and frm.fields_dict["field"]."""
        name = self.string(node.child_by_field_name("index"))
        obj = node.child_by_field_name("object")
        if name is None or obj is None:
            return
        owner = self.typed(obj, env)
        if owner and owner[0] == "doc":
            self.add(owner[1], name, node)
        elif obj.type == "member_expression":
            inner = obj.child_by_field_name("property")
            frm = self.typed(obj.child_by_field_name("object"), env)
            if frm and frm[0] == "frm" and inner is not None and self.text(inner) == "fields_dict":
                self.add(frm[1], name, node)

    def call_ref(self, call: Node, env: _Env) -> None:
        """frm.set_value("field", ...) and similar methods; frappe.model.* on the current row."""
        callee = call.child_by_field_name("function")
        arguments = self.args(call)
        if callee is None or not arguments:
            return
        if callee.type == "member_expression":
            frm = self.typed(callee.child_by_field_name("object"), env)
            method = callee.child_by_field_name("property")
            if frm and frm[0] == "frm" and method is not None:
                self.frm_method(self.text(method), arguments, frm[1])
                return
        path = self.dotted(callee)
        if env.cd and path in ("frappe.model.get_value", "frappe.model.set_value"):
            first = self.text(arguments[0])  # frappe.model.set_value(cdt, cdn, "field", value)
            if first == env.cd[0] and len(arguments) >= 3:
                self.names(arguments[2], env.cd[2])

    def frm_method(self, method: str, arguments: list[Node], doctype: str) -> None:
        """Record the field named by the first argument of a form method."""
        if method not in FRM_FIELD_METHODS:
            return
        if method == "set_df_property" and len(arguments) >= 5:
            return  # a table_field argument means the field belongs to the child table
        if method == "set_query" and len(arguments) >= 2 and self.string(arguments[1]) is not None:
            return  # frm.set_query("child_field", "table_field", fn)
        self.names(arguments[0], doctype)
        if method == "set_currency_labels" and len(arguments) >= 3:
            self.names(arguments[2], doctype)  # the parentfield (a table field of this form)


def js_refs(source: bytes) -> tuple[list[FieldRef], list[tuple[str, int]], bool]:
    """Field refs, DocType-name refs, and whether the file had syntax errors."""
    tree = _PARSER.parse(source)
    scan = _Scan(source)
    scan.general(tree.root_node)
    scan.forms_and_lists(tree.root_node)
    return scan.fields, scan.doctypes, tree.root_node.has_error