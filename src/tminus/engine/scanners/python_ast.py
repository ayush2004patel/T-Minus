"""Scan Python source with the stdlib ast module."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable

from tminus.engine.matchers import MATCHERS
from tminus.engine.models import Finding, Rule

_IGNORE_RE = re.compile(r"#\s*tminus:\s*ignore\[([^\]]*)\]")  # "# tminus: ignore[rule-id]"


def _ignored_ids(line: str) -> set[str]:
    """Return rule ids suppressed by an ignore comment on this line."""
    match = _IGNORE_RE.search(line)
    if not match:
        return set()
    return {part.strip() for part in match.group(1).split(",") if part.strip()}


def scan_source(source: str, filename: str, rules: Iterable[Rule]) -> list[Finding]:
    """Run all rules over one file's source; raises SyntaxError if it cannot be parsed."""
    tree = ast.parse(source, filename=filename)
    lines = source.splitlines()
    findings: list[Finding] = []
    for rule in rules:
        matcher = MATCHERS.get(rule.match.type)
        if matcher is None:  # rule type not implemented yet
            continue
        for lineno in matcher(tree, rule):
            text = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
            if rule.id in _ignored_ids(text):  # suppressed by comment
                continue
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    category=rule.category,
                    stage=rule.stage,
                    file=filename,
                    line=lineno,
                    snippet=text.strip(),
                    message=rule.message.strip(),
                    replacement=rule.replacement.strip(),
                )
            )
    return sorted(findings, key=lambda f: (f.file, f.line, f.rule_id))
