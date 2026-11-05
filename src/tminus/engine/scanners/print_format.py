"""Scan standard Print Formats (JSON + Jinja template) for removed fields and DocTypes."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from tminus.engine.frappe_refs import FieldRef
from tminus.engine.jinja_refs import jinja_refs
from tminus.engine.models import Finding, Rule
from tminus.engine.paths import is_skipped
from tminus.engine.ref_rules import apply_ref_rules


def find_print_format_files(root: Path) -> Iterator[Path]:
    """Yield the JSON files that live in a `print_format` folder."""
    if root.is_file():
        return
    for path in sorted(root.rglob("*.json")):
        if "print_format" in path.relative_to(root).parts[:-1] and not is_skipped(root, path):
            yield path


def _key_line(raw: str, key: str) -> int:
    """Line number (1-based) where a JSON key starts, or 1."""
    match = re.search(rf'"{re.escape(key)}"\s*:', raw)
    return 1 + raw.count("\n", 0, match.start()) if match else 1


def _builder_items(format_data: str) -> tuple[list[str], list[str]]:
    """Field names listed by the Print Format Builder, and its Custom HTML blocks."""
    try:
        items = json.loads(format_data)
    except ValueError:
        return [], []
    names: list[str] = []
    html_blocks: list[str] = []
    for item in items if isinstance(items, list) else []:  # nested visible_columns are not read
        if not isinstance(item, dict):
            continue
        if item.get("fieldtype") == "Custom HTML" and isinstance(item.get("options"), str):
            html_blocks.append(item["options"])
        elif isinstance(item.get("fieldname"), str) and item["fieldname"]:
            names.append(item["fieldname"])
    return names, html_blocks


def _scan_one(
    path: Path, raw: str, item: dict[str, Any], rules: list[Rule]
) -> tuple[list[Finding], list[str]]:
    """Findings and notes for one Print Format document."""
    doctype = item.get("doc_type")
    if not isinstance(doctype, str) or item.get("print_format_type") not in (None, "Jinja"):
        return [], []
    context = f'print format "{item.get("name", path.stem)}" for {doctype}'
    findings: list[Finding] = []
    notes: list[str] = []

    def template(text: str, file: Path, lines: list[str], fixed_line: int | None) -> None:
        """Scan one Jinja template and add its findings."""
        fields, doctypes, unparsable = jinja_refs(text, doctype)
        if unparsable:
            notes.append(f"{file}: {unparsable} Jinja expressions could not be parsed, not checked")
        findings.extend(
            apply_ref_rules(rules, fields, doctypes, str(file), lines, context, fixed_line)
        )

    sibling = path.with_suffix(".html")
    if sibling.is_file():  # the usual layout: foo/foo.json + foo/foo.html
        html = sibling.read_text(encoding="utf-8")
        template(html, sibling, html.splitlines(), None)
    elif isinstance(item.get("html"), str):  # template stored inside the JSON string
        template(item["html"], path, raw.splitlines(), _key_line(raw, "html"))
    if isinstance(item.get("format_data"), str):  # Print Format Builder layout
        line = _key_line(raw, "format_data")
        names, blocks = _builder_items(item["format_data"])
        refs = [FieldRef(doctype, name, line) for name in names]
        findings.extend(apply_ref_rules(rules, refs, [], str(path), raw.splitlines(), context))
        for block in blocks:
            template(block, path, raw.splitlines(), line)
    return findings, notes


def scan_print_formats(root: Path, rules: Iterable[Rule]) -> tuple[list[Finding], list[str], int]:
    """Scan every standard Print Format under root; returns findings, notes and a file count."""
    rule_list = list(rules)
    findings: list[Finding] = []
    notes: list[str] = []
    count = 0
    for path in find_print_format_files(root):
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, UnicodeDecodeError, ValueError):
            continue  # not a Print Format document (or unreadable)
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("doctype") == "Print Format":
                found, found_notes = _scan_one(path, raw, item, rule_list)
                findings.extend(found)
                notes.extend(found_notes)
                count += 1
    return findings, notes, count