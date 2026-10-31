"""Scan one Python file with the stdlib ast module (per-file rules)."""

from __future__ import annotations

import ast
from collections.abc import Iterable

from tminus.engine.matchers import MATCHERS
from tminus.engine.models import Finding, Rule
from tminus.engine.suppress import ignored_ids


def scan_source(source: str, filename: str, rules: Iterable[Rule]) -> list[Finding]:
    """Run all per-file rules over one file's source; raises SyntaxError if unparsable."""
    tree = ast.parse(source, filename=filename)
    lines = source.splitlines()
    findings: list[Finding] = []
    for rule in rules:
        matcher = MATCHERS.get(rule.match.type)
        if matcher is None:  # app-level rule types are handled by scanners/hooks.py
            continue
        for lineno in matcher(tree, rule):
            text = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
            if rule.id in ignored_ids(text):  # suppressed by comment
                continue
            findings.append(Finding.from_rule(rule, filename, lineno, text))
    return sorted(findings, key=lambda f: (f.file, f.line, f.rule_id))
