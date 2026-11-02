"""Matchers: one function per rule match type."""

from __future__ import annotations

from collections.abc import Callable

from tminus.engine.context import FileContext
from tminus.engine.matchers.call import match_call
from tminus.engine.matchers.doctype import match_doctype_field, match_doctype_name
from tminus.engine.matchers.import_path import match_import_path
from tminus.engine.models import Hit, Rule

Matcher = Callable[[FileContext, Rule], list[Hit]]  # returns where the rule matched

MATCHERS: dict[str, Matcher] = {
    "import_path": match_import_path,
    "call": match_call,
    "doctype_field": match_doctype_field,
    "doctype_name": match_doctype_name,
}
