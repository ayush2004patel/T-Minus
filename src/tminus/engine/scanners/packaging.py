"""App-level scanner: packaging compatibility (Python range, frappe bound, pins, Node)."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from tminus.engine.app_packaging import AppPackaging, Where, read_app
from tminus.engine.models import Finding, PackageMatch, Rule
from tminus.engine.scanners.hooks import find_hooks_files
from tminus.engine.suppress import ignored_ids
from tminus.engine.versions import node_allows, spec_allows, specs_conflict

UPSTREAM_APPS = {"frappe", "erpnext", "hrms"}  # installed from their own version-16 branch


def _rejects_all(spec: str, versions: list[str], allows: object = spec_allows) -> bool:
    """True if the range is readable and allows none of the versions."""
    results = [allows(spec, v) for v in versions]  # type: ignore[operator]
    return all(r is False for r in results)


def _range_hit(
    where: Where | None, what: str, versions: list[str], node: bool = False
) -> list[tuple[Path, int, str]]:
    """A hit when a version range rejects every listed version."""
    if where is None:
        return []
    allows = node_allows if node else spec_allows
    if _rejects_all(where.value, versions, allows):
        return [(where.file, where.line, f'{what} "{where.value}" excludes {", ".join(versions)}')]
    return []


def package_hits(match: PackageMatch, app: AppPackaging) -> list[tuple[Path, int, str]]:
    """(file, line, detail) for each way this app breaks one packaging rule."""
    if match.check == "requires_python":
        return _range_hit(app.requires_python, "requires Python", match.versions)
    if match.check == "frappe_bound":
        return _range_hit(app.frappe_bound, "frappe-dependencies requires frappe", match.versions)
    if match.check == "node_engine":
        return _range_hit(app.node_engine, "engines.node", match.versions, node=True)
    if match.check == "frappe_bound_missing":
        if app.frappe_bound is None:
            return [
                (app.anchor, 1, f"{app.name}: no [tool.bench.frappe-dependencies] frappe bound")
            ]
        return []
    hits: list[tuple[Path, int, str]] = []  # dependency_pins
    for dep in app.dependencies:
        pin = match.pins.get(dep.name)
        if pin is not None and dep.spec and specs_conflict(dep.spec, pin) is True:
            hits.append(
                (
                    dep.where.file,
                    dep.where.line,
                    f"{dep.name}{dep.spec} conflicts with frappe's {dep.name}{pin}",
                )
            )
    return hits


def scan_packaging(root: Path, rules: Iterable[Rule]) -> tuple[list[Finding], list[str], int]:
    """Check the packaging of every app under root; returns findings, notes and an app count."""
    rule_list = [r for r in rules if isinstance(r.match, PackageMatch)]
    findings: list[Finding] = []
    notes: list[str] = []
    count = 0
    if not rule_list:
        return findings, notes, count
    for app_root in sorted({hooks.parent.parent for hooks in find_hooks_files(root)}):
        app = read_app(app_root)
        if app is None:
            notes.append(
                f"{app_root}: no pyproject.toml/setup.py/requirements.txt, packaging not checked"
            )
            continue
        if app.name in UPSTREAM_APPS or app_root.name in UPSTREAM_APPS:
            continue
        count += 1
        for rule in rule_list:
            if not isinstance(rule.match, PackageMatch):
                continue
            for file, line, detail in package_hits(rule.match, app):
                lines = file.read_text(encoding="utf-8").splitlines() if file.is_file() else []
                text = lines[line - 1] if 0 < line <= len(lines) else ""
                if rule.id not in ignored_ids(text):  # `# tminus: ignore[...]` in pyproject.toml
                    findings.append(Finding.from_rule(rule, str(file), line, text, detail))
    return sorted(findings, key=lambda f: (f.file, f.line, f.rule_id)), notes, count
