"""Scan one client-side JavaScript file for removed fields and DocTypes."""

from __future__ import annotations

from collections.abc import Iterable

from tminus.engine.js_refs import js_refs
from tminus.engine.models import Finding, Rule
from tminus.engine.ref_rules import apply_ref_rules


def scan_js(source: bytes, filename: str, rules: Iterable[Rule]) -> tuple[list[Finding], bool]:
    """Findings for one JS file, and whether it had syntax errors (then only partly checked)."""
    fields, doctypes, has_errors = js_refs(source)
    lines = source.decode("utf-8", "replace").splitlines()
    return apply_ref_rules(rules, fields, doctypes, filename, lines), has_errors
