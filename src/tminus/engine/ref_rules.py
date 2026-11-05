"""Apply the field and DocType rules to references found in non-Python files."""

from __future__ import annotations

from collections.abc import Iterable

from tminus.engine.frappe_refs import FieldRef
from tminus.engine.matchers.doctype import field_hits, name_hits
from tminus.engine.models import DoctypeFieldMatch, DoctypeNameMatch, Finding, Rule
from tminus.engine.suppress import ignored_ids

MAX_SNIPPET = 160  # minified files and JSON strings can have enormous lines


def apply_ref_rules(
    rules: Iterable[Rule],
    field_refs: list[FieldRef],
    doctype_refs: list[tuple[str, int]],
    filename: str,
    lines: list[str],
    context: str = "",
    fixed_line: int | None = None,
) -> list[Finding]:
    """Findings for references to removed fields/DocTypes.

    `fixed_line` reports every hit on one line (for text embedded in a JSON string).
    """
    findings: dict[tuple[str, int, str, str], Finding] = {}
    for rule in rules:
        match = rule.match
        if isinstance(match, DoctypeFieldMatch):
            hits = field_hits(match, field_refs)
        elif isinstance(match, DoctypeNameMatch):
            hits = name_hits(match, doctype_refs)
        else:
            continue
        for hit in hits:
            line = fixed_line if fixed_line is not None else hit.line
            text = lines[line - 1] if 0 < line <= len(lines) else ""
            if rule.id in ignored_ids(text):
                continue
            detail = hit.detail
            if fixed_line is not None:
                detail += f"  (line {hit.line} of the template)"
            if context:
                detail += f"  ({context})"
            snippet = text.strip()[:MAX_SNIPPET]
            finding = Finding.from_rule(rule, filename, line, snippet, detail)
            findings[(filename, line, rule.id, detail)] = finding
    return sorted(findings.values(), key=lambda f: (f.file, f.line, f.rule_id))
