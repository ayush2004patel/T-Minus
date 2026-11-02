"""Matchers for removed or renamed fields and for removed DocTypes."""

from __future__ import annotations

from tminus.engine.context import FileContext
from tminus.engine.models import DoctypeFieldMatch, DoctypeNameMatch, Hit, Rule


def match_doctype_field(ctx: FileContext, rule: Rule) -> list[Hit]:
    """Flag fields that no longer exist on a DocType whose name the code states."""
    match = rule.match
    if not isinstance(match, DoctypeFieldMatch):  # wrong rule type for this matcher
        return []
    hits: dict[tuple[int, str], Hit] = {}
    for ref in ctx.field_refs:
        note = match.doctypes.get(ref.doctype, {}).get(ref.name)
        if note is not None:
            hit = Hit(line=ref.line, detail=f"{ref.doctype}.{ref.name}: {note}")
            hits[(hit.line, hit.detail)] = hit  # one finding per line and field
    return sorted(hits.values(), key=lambda h: (h.line, h.detail))


def match_doctype_name(ctx: FileContext, rule: Rule) -> list[Hit]:
    """Flag DocTypes that no longer exist when they are passed to a Frappe API."""
    match = rule.match
    if not isinstance(match, DoctypeNameMatch):  # wrong rule type for this matcher
        return []
    hits: dict[tuple[int, str], Hit] = {}
    for name, line in ctx.doctype_refs:
        note = match.names.get(name)
        if note is not None:
            hit = Hit(line=line, detail=f"{name}: {note}")
            hits[(hit.line, hit.detail)] = hit
    return sorted(hits.values(), key=lambda h: (h.line, h.detail))
