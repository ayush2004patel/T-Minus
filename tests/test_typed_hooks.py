"""Tests for field detection through hook parameters (doc_events, has_permission, overrides)."""

from pathlib import Path

from tminus.engine.loader import load_rules
from tminus.engine.models import Finding
from tminus.engine.runner import scan_path

RULES = load_rules("v16")
ERP = "v16-erpnext-removed-or-renamed-fields"


def _scan(tmp_path: Path, hooks: str, files: dict[str, str]) -> list[Finding]:
    """Create an app `myapp` and return the findings of the ERPNext field rule."""
    pkg = tmp_path / "myapp"
    pkg.mkdir()
    (pkg / "hooks.py").write_text(hooks)
    for name, content in files.items():
        (pkg / name).write_text(content)
    return [f for f in scan_path(tmp_path, RULES).findings if f.rule_id == ERP]


def test_doc_events_parameter_is_typed(tmp_path: Path) -> None:
    """The first parameter of a doc_events function is a document of that DocType."""
    hooks = 'doc_events = {"Quotation": {"validate": "myapp.events.check"}}\n'
    events = "def check(doc, method=None):\n    return doc.source\n"
    (found,) = _scan(tmp_path, hooks, {"events.py": events})
    assert found.file.endswith("events.py")
    assert found.line == 2
    assert 'via doc_events["Quotation"]["validate"]' in found.detail


def test_doc_events_list_of_functions(tmp_path: Path) -> None:
    """A list of functions for one event is checked function by function."""
    hooks = 'doc_events = {"Quotation": {"validate": ["myapp.events.a", "myapp.events.b"]}}\n'
    events = (
        "def a(doc, method=None):\n    doc.source\n\n\ndef b(doc, method=None):\n    doc.campaign\n"
    )
    assert len(_scan(tmp_path, hooks, {"events.py": events})) == 2


def test_doc_get_and_set_through_parameter(tmp_path: Path) -> None:
    """doc.get("f") is checked through the hook parameter."""
    hooks = 'doc_events = {"Sales Invoice": {"on_submit": "myapp.events.check"}}\n'
    events = 'def check(doc, method=None):\n    return doc.get("campaign")\n'
    assert len(_scan(tmp_path, hooks, {"events.py": events})) == 1


def test_wildcard_doctype_is_skipped(tmp_path: Path) -> None:
    """The "*" key means every DocType, so no single type can be assumed."""
    hooks = 'doc_events = {"*": {"validate": "myapp.events.check"}}\n'
    events = "def check(doc, method=None):\n    return doc.source\n"
    assert _scan(tmp_path, hooks, {"events.py": events}) == []


def test_other_doctype_is_not_flagged(tmp_path: Path) -> None:
    """Issue.source is not a removed field."""
    hooks = 'doc_events = {"Issue": {"validate": "myapp.events.check"}}\n'
    events = "def check(doc, method=None):\n    return doc.source\n"
    assert _scan(tmp_path, hooks, {"events.py": events}) == []


def test_current_field_is_fine(tmp_path: Path) -> None:
    """The new field name is clean."""
    hooks = 'doc_events = {"Quotation": {"validate": "myapp.events.check"}}\n'
    events = "def check(doc, method=None):\n    return doc.utm_source\n"
    assert _scan(tmp_path, hooks, {"events.py": events}) == []


def test_reassigned_parameter_is_not_guessed(tmp_path: Path) -> None:
    """If the function reassigns `doc`, its type is unknown afterwards."""
    hooks = 'doc_events = {"Quotation": {"validate": "myapp.events.check"}}\n'
    events = "def check(doc, method=None):\n    doc = other()\n    return doc.source\n"
    assert _scan(tmp_path, hooks, {"events.py": events}) == []


def test_not_reported_twice_with_a_local_typed_variable(tmp_path: Path) -> None:
    """A variable typed by get_doc inside the hook is found once, by the per-file pass."""
    hooks = 'doc_events = {"Quotation": {"validate": "myapp.events.check"}}\n'
    events = (
        "import frappe\n\n\n"
        "def check(doc, method=None):\n"
        '    q = frappe.get_doc("Quotation", doc.name)\n'
        "    return q.source\n"
    )
    assert len(_scan(tmp_path, hooks, {"events.py": events})) == 1


def test_has_permission_parameter_is_typed(tmp_path: Path) -> None:
    """The document passed to a has_permission function has the hook's DocType."""
    hooks = 'has_permission = {"Quotation": "myapp.perm.check"}\n'
    perm = "def check(doc, ptype, user):\n    return doc.source is not None\n"
    (found,) = _scan(tmp_path, hooks, {"perm.py": perm})
    assert 'via has_permission["Quotation"]' in found.detail


def test_override_class_self_is_typed(tmp_path: Path) -> None:
    """Inside an override_doctype_class class, `self` is the overridden DocType."""
    hooks = 'override_doctype_class = {"Quotation": "myapp.over.Custom"}\n'
    over = (
        "class Custom(Base):\n"
        "    def validate(self):\n"
        "        return self.source\n"
        "\n"
        "    @staticmethod\n"
        "    def helper(x):\n"
        "        return x.source\n"
    )
    (found,) = _scan(tmp_path, hooks, {"over.py": over})
    assert found.line == 3
    assert 'via override_doctype_class["Quotation"]' in found.detail


def test_non_literal_doc_events_is_listed(tmp_path: Path) -> None:
    """A doc_events table built at run time is reported as not checked."""
    pkg = tmp_path / "myapp"
    pkg.mkdir()
    (pkg / "hooks.py").write_text("doc_events = build()\n")
    result = scan_path(tmp_path, RULES)
    assert any("doc_events is not a literal dict" in note for note in result.skipped)


def test_ignore_comment_in_hook_function(tmp_path: Path) -> None:
    """A tminus ignore comment suppresses a hook-parameter finding."""
    hooks = 'doc_events = {"Quotation": {"validate": "myapp.events.check"}}\n'
    events = f"def check(doc, method=None):\n    return doc.source  # tminus: ignore[{ERP}]\n"
    assert _scan(tmp_path, hooks, {"events.py": events}) == []


def test_tuple_of_doctypes_as_key(tmp_path: Path) -> None:
    """Frappe allows ("A", "B") as a doc_events key; every listed DocType is checked."""
    hooks = 'doc_events = {("Quotation", "Issue"): {"validate": "myapp.events.check"}}\n'
    events = "def check(doc, method=None):\n    return doc.source\n"
    found = _scan(tmp_path, hooks, {"events.py": events})
    assert len(found) == 1  # Quotation.source is removed, Issue.source is not
    assert 'doc_events["Quotation"]' in found[0].detail


def test_computed_key_skips_only_that_entry(tmp_path: Path) -> None:
    """A computed key is listed as not checked; the other entries are still scanned."""
    hooks = (
        'doc_events = {tuple(names): {"validate": "myapp.events.check"},\n'
        '              "Quotation": {"validate": "myapp.events.check"}}\n'
    )
    events = "def check(doc, method=None):\n    return doc.source\n"
    pkg = tmp_path / "myapp"
    pkg.mkdir()
    (pkg / "hooks.py").write_text(hooks)
    (pkg / "events.py").write_text(events)
    result = scan_path(tmp_path, RULES)
    assert len([f for f in result.findings if f.rule_id == ERP]) == 1
    assert any("1 doc_events entries not checked" in note for note in result.skipped)
