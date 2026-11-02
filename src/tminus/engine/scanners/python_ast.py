"""Scan one Python file with the stdlib ast module (per-file rules)."""

from __future__ import annotations

import ast
from collections.abc import Iterable

from tminus.engine.context import FileContext
from tminus.engine.matchers import MATCHERS
from tminus.engine.models import Finding, Rule
from tminus.engine.suppress import ignored_ids


def scan_source(source: str, filename: str, rules: Iterable[Rule]) -> list[Finding]:
    """Run all per-file rules over one file's source; raises SyntaxError if unparsable."""
    ctx = FileContext.build(ast.parse(source, filename=filename))  # facts computed once per file
    lines = source.splitlines()
    findings: list[Finding] = []
    for rule in rules:
        matcher = MATCHERS.get(rule.match.type)
        if matcher is None:  # app-level rule types are handled by scanners/hooks.py
            continue
        for hit in matcher(ctx, rule):
            lineno = hit.line
            text = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
            if rule.id in ignored_ids(text):  # suppressed by comment
                continue
            findings.append(Finding.from_rule(rule, filename, lineno, text, hit.detail))
    return sorted(findings, key=lambda f: (f.file, f.line, f.rule_id))
