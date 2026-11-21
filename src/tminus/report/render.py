"""Turn a ScanResult into terminal, web and machine-readable reports."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path
from typing import Any

from tminus.engine.models import Finding, Rule, ScanResult

NOT_CHECKED = [  # honest list of what is not covered yet
    "Static checks only: Python, JavaScript, Print Format templates, hooks, SQL text, packaging.",
    "Not implemented yet: site data, site-saved code, migrate rehearsal, v15 vs v16 comparison.",
]

STAGE_ORDER = ["T-30", "T-14", "T-7", "T-3", "T-1", "T-0"]  # the countdown, earliest first
SEVERITIES = ("error", "warning", "info")
_SEVERITY_HEADINGS = {
    "error": ("Errors", "ACTION REQUIRED", "These findings are likely to break on v16."),
    "warning": ("Warnings", "REVIEW REQUIRED", "These findings need a developer's review."),
    "info": (
        "Information",
        "BEHAVIOR REVIEW",
        "These findings may change behavior without an error.",
    ),
}
_COLORS = {"error": "31;1", "warning": "33;1", "info": "36;1"}
_HTML_CSS = """
body { background: #f6f8fa; color: #1f2328; font: 16px/1.5 system-ui, sans-serif; margin: 0; }
main { max-width: 1000px; margin: 0 auto; padding: 2rem 1rem 4rem; }
header, section, footer {
  background: #fff; border: 1px solid #d0d7de; border-radius: 8px; padding: 1.25rem;
  margin-top: 1rem;
}
h1, h2, h3 { line-height: 1.25; }
h1 { margin-top: 0; }
h2 { border-bottom: 1px solid #d0d7de; padding-bottom: .5rem; }
.result { border-left: 6px solid #0969da; }
.error { border-left-color: #cf222e; }
.warning { border-left-color: #9a6700; }
.info { border-left-color: #0969da; }
.status { font-weight: 700; }
.status.error { color: #cf222e; }
.status.warning { color: #9a6700; }
.status.info { color: #0969da; }
.rule {
  border: 1px solid #d0d7de; border-left: 5px solid #0969da; border-radius: 6px;
  margin: 1rem 0; padding: 1rem;
}
.rule.error { border-left-color: #cf222e; }
.rule.warning { border-left-color: #9a6700; }
.meta { color: #57606a; }
code { background: #f6f8fa; border-radius: 4px; padding: .1rem .3rem; }
pre {
  background: #f6f8fa; border-radius: 4px; margin: .4rem 0; overflow-x: auto;
  padding: .75rem; white-space: pre-wrap;
}
details { margin-top: .75rem; }
li { margin: .75rem 0; }
.note { color: #57606a; }
"""


def _counts_text(counts: Mapping[str, int], keys: tuple[str, ...]) -> str:
    """`2 error, 1 warning` for the keys that have findings."""
    return ", ".join(f"{counts[k]} {k}" for k in keys if counts[k])


def summarize(result: ScanResult) -> dict[str, Any]:
    """Counts of findings by severity, by stage (with severities) and by category."""
    by_stage: dict[str, Counter[str]] = {}
    for f in result.findings:
        by_stage.setdefault(f.stage, Counter())[f.severity] += 1
    return {
        "total": len(result.findings),
        "by_severity": dict(Counter(f.severity for f in result.findings)),
        "by_stage": {stage: dict(by_stage[stage]) for stage in STAGE_ORDER if stage in by_stage},
        "by_category": dict(Counter(f.category for f in result.findings)),
        "baselined": result.baselined,
    }


def render_text(
    result: ScanResult,
    target: str,
    rules: Sequence[Rule] = (),
    app_name: str | None = None,
    color: bool = False,
) -> str:
    """Render a developer-facing checklist grouped by upgrade problem and severity."""
    titles = {rule.id: rule.title for rule in rules}
    out = [_paint("T-MINUS scan report", "1;34", color), f"Target upgrade: v15 → {target}"]
    if app_name:
        out.append(f"Application: {app_name}")
    out.extend([f"Files scanned: {result.files_scanned}", ""])
    out.extend(_overview_lines(result, color))
    for severity in SEVERITIES:
        findings = [finding for finding in result.findings if finding.severity == severity]
        if findings:
            out.extend(_rule_groups(severity, findings, titles, color))
    out.extend(_summary_lines(result))
    out.append("")
    out.append("Not checked:")
    out.extend(f"  - {line}" for line in NOT_CHECKED)
    out.extend(f"  - skipped {line}" for line in result.skipped)
    return "\n".join(out)


def _paint(text: str, code: str, color: bool) -> str:
    """Apply an ANSI style only when terminal color was requested."""
    return f"\033[{code}m{text}\033[0m" if color else text


def _overview_lines(result: ScanResult, color: bool) -> list[str]:
    """Plain-language result and next steps before the detailed evidence."""
    counts: Counter[str] = Counter(str(f.severity) for f in result.findings)
    if not result.findings:
        result_line = (
            "Result: no new known issues." if result.baselined else "Result: no known issues."
        )
        return [result_line, ""]
    if counts["error"]:
        result_line = f"Result: {_paint('ACTION REQUIRED', _COLORS['error'], color)}"
    elif counts["warning"]:
        result_line = f"Result: {_paint('REVIEW REQUIRED', _COLORS['warning'], color)}"
    else:
        result_line = f"Result: {_paint('BEHAVIOR REVIEW', _COLORS['info'], color)}"
    next_steps = [
        result_line,
        f"Findings: {_counts_text(counts, SEVERITIES)}",
        "",
        "What to do next:",
    ]
    if counts["error"]:
        next_steps.append("  1. Resolve Errors before an upgrade rehearsal.")
    if counts["warning"]:
        next_steps.append("  2. Review Warnings before migrating.")
    if counts["info"]:
        next_steps.append("  3. Review Information findings for behavior changes.")
    next_steps.extend(
        [
            "",
            "This is a static scan. Confirm changes on a restored copy before upgrading",
            "production.",
            "",
        ]
    )
    return next_steps


def _rule_groups(
    severity: str, findings: list[Finding], titles: dict[str, str], color: bool
) -> list[str]:
    """Render findings by rule so one upgrade change has one explanation and checklist."""
    heading, status, guidance = _SEVERITY_HEADINGS[severity]
    out = [_paint(f"{heading} ({len(findings)})", _COLORS[severity], color), f"  {guidance}"]
    by_rule: dict[str, list[Finding]] = {}
    for finding in findings:
        by_rule.setdefault(finding.rule_id, []).append(finding)
    for number, rule_id in enumerate(sorted(by_rule), start=1):
        rule_findings = sorted(by_rule[rule_id], key=lambda f: (f.file, f.line))
        first = rule_findings[0]
        title = titles.get(rule_id, rule_id)
        out.append(f"  {number}. {title} ({len(rule_findings)} location(s))")
        out.append(
            f"     Status: {_paint(status, _COLORS[severity], color)} • Rule: {rule_id} "
            f"• [{first.category}, {first.stage}]"
        )
        out.append(f"     Why it matters: {first.message}")
        out.append(f"     Suggested action: {first.replacement}")
        out.append("     Affected locations:")
        for finding in rule_findings:
            out.append(f"       - {finding.file}:{finding.line}")
            out.append(f"         Code: {finding.snippet}")
            if finding.detail:
                out.append(f"         Technical context: {finding.detail}")
    return [*out, ""]


def _summary_lines(result: ScanResult) -> list[str]:
    """The summary block at the end of the text report."""
    hidden = f" ({result.baselined} hidden by the baseline)" if result.baselined else ""
    if not result.findings:
        return [("No new findings." if result.baselined else "No findings.") + hidden]
    summary = summarize(result)
    severities = Counter(summary["by_severity"])
    lines = [f"Summary: {_counts_text(severities, SEVERITIES)}{hidden}"]
    stages = [
        f"{stage}: {_counts_text(Counter(counts), SEVERITIES)}"
        for stage, counts in summary["by_stage"].items()
    ]
    lines.append("  by stage:    " + "; ".join(stages))
    categories = Counter(summary["by_category"])
    lines.append("  by category: " + _counts_text(categories, ("data", "loud", "quiet", "silent")))
    return lines


def render_json(result: ScanResult, target: str) -> str:
    """Machine-readable report for CI; it can also be used as a baseline."""
    payload = {
        "target": target,
        "summary": summarize(result),
        "result": result.model_dump(mode="json"),
    }
    return json.dumps(payload, indent=2)


def render_sarif(result: ScanResult, target: str, rules: Sequence[Rule], root: Path) -> str:
    """Render findings as a SARIF 2.1.0 log for code-scanning tools."""
    source_root = root.parent if root.is_file() else root
    rule_map = {rule.id: rule for rule in rules}
    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "T-MINUS",
                        "informationUri": "https://github.com/kaulith/tminus",
                        "rules": [_sarif_rule(rule) for rule in rules],
                    }
                },
                "originalUriBaseIds": {"SRCROOT": {"uri": _directory_uri(source_root)}},
                "results": [
                    _sarif_result(finding, rule_map.get(finding.rule_id), source_root)
                    for finding in result.findings
                ],
            }
        ],
    }
    return json.dumps(payload, indent=2)


def _sarif_rule(rule: Rule) -> dict[str, Any]:
    """Convert a T-MINUS rule into SARIF rule metadata."""
    descriptor: dict[str, Any] = {
        "id": rule.id,
        "name": rule.id,
        "shortDescription": {"text": rule.title},
        "fullDescription": {"text": rule.message},
        "help": {"text": rule.replacement},
        "defaultConfiguration": {"level": _sarif_level(rule.severity)},
        "properties": {
            "category": rule.category,
            "stage": rule.stage,
            "fixTiming": rule.fix,
            "autofix": rule.autofix,
            "confidence": rule.confidence,
            "references": rule.references,
        },
    }
    reference = next(
        (ref for ref in rule.references if ref.startswith(("http://", "https://"))), None
    )
    if reference:
        descriptor["helpUri"] = reference
    return descriptor


def _sarif_result(finding: Finding, rule: Rule | None, source_root: Path) -> dict[str, Any]:
    """Convert one finding into a SARIF result with its source location."""
    location = Path(finding.file)
    try:
        uri = location.resolve().relative_to(source_root.resolve()).as_posix()
        artifact: dict[str, str] = {"uri": uri, "uriBaseId": "SRCROOT"}
    except ValueError:
        artifact = {"uri": location.resolve().as_uri()}
    properties: dict[str, Any] = {
        "category": finding.category,
        "stage": finding.stage,
        "suggestedAction": finding.replacement,
        "technicalContext": finding.detail,
    }
    if rule is not None:
        properties["references"] = rule.references
    return {
        "ruleId": finding.rule_id,
        "level": _sarif_level(finding.severity),
        "message": {"text": finding.message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": artifact,
                    "region": {"startLine": finding.line, "snippet": {"text": finding.snippet}},
                }
            }
        ],
        "properties": properties,
    }


def _sarif_level(severity: str) -> str:
    """Map T-MINUS severities to the SARIF severity vocabulary."""
    return {"error": "error", "warning": "warning", "info": "note"}[severity]


def _directory_uri(path: Path) -> str:
    """Return a file URI that identifies a directory as a SARIF base URI."""
    return f"{path.resolve().as_uri()}/"


def render_html(
    result: ScanResult,
    target: str,
    rules: Sequence[Rule] = (),
    app_name: str | None = None,
) -> str:
    """Render a self-contained, browser-friendly version of the text report."""
    titles = {rule.id: rule.title for rule in rules}
    counts: Counter[str] = Counter(str(f.severity) for f in result.findings)
    overall = "error" if counts["error"] else "warning" if counts["warning"] else "info"
    name = app_name or "application"
    out = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(name)} — T-MINUS scan report</title>",
        f"<style>{_HTML_CSS}</style></head><body><main>",
        "<header>",
        "<h1>T-MINUS scan report</h1>",
        f"<p><strong>Target upgrade:</strong> v15 → {escape(target)}<br>",
        f"<strong>Application:</strong> {escape(name)}<br>",
        f"<strong>Files scanned:</strong> {result.files_scanned}</p>",
        "</header>",
    ]
    out.extend(_html_overview(result, counts, overall))
    for severity in SEVERITIES:
        findings = [finding for finding in result.findings if finding.severity == severity]
        if findings:
            out.extend(_html_rule_groups(severity, findings, titles))
    out.append("<footer><h2>Not checked</h2><ul>")
    out.extend(f"<li>{escape(note)}</li>" for note in NOT_CHECKED)
    out.extend(f"<li>{escape('Skipped: ' + note)}</li>" for note in result.skipped)
    out.append("</ul></footer></main></body></html>")
    return "\n".join(out)


def _html_overview(result: ScanResult, counts: Counter[str], overall: str) -> list[str]:
    """Render the HTML report's plain-language result and next steps."""
    if not result.findings:
        message = "No new known issues." if result.baselined else "No known issues."
        return [f'<section class="result info"><h2>Result: {message}</h2></section>']
    _, status, _ = _SEVERITY_HEADINGS[overall]
    out = [
        f'<section class="result {overall}">',
        f'<h2>Result: <span class="status {overall}">{status}</span></h2>',
        f"<p><strong>Findings:</strong> {escape(_counts_text(counts, SEVERITIES))}</p>",
        "<h3>What to do next</h3><ol>",
    ]
    if counts["error"]:
        out.append("<li>Resolve Errors before an upgrade rehearsal.</li>")
    if counts["warning"]:
        out.append("<li>Review Warnings before migrating.</li>")
    if counts["info"]:
        out.append("<li>Review Information findings for behavior changes.</li>")
    out.extend(
        [
            "</ol>",
            '<p class="note">This is a static scan. Confirm changes on a restored copy '
            "before upgrading production.</p>",
            "</section>",
        ]
    )
    return out


def _html_rule_groups(severity: str, findings: list[Finding], titles: dict[str, str]) -> list[str]:
    """Render all locations for each rule as accessible HTML cards."""
    heading, status, guidance = _SEVERITY_HEADINGS[severity]
    out = [f'<section class="{severity}">', f"<h2>{escape(heading)} ({len(findings)})</h2>"]
    out.append(f"<p>{escape(guidance)}</p>")
    by_rule: dict[str, list[Finding]] = {}
    for finding in findings:
        by_rule.setdefault(finding.rule_id, []).append(finding)
    for number, rule_id in enumerate(sorted(by_rule), start=1):
        rule_findings = sorted(by_rule[rule_id], key=lambda f: (f.file, f.line))
        first = rule_findings[0]
        title = titles.get(rule_id, rule_id)
        out.extend(
            [
                f'<article class="rule {severity}">',
                f"<h3>{number}. {escape(title)} ({len(rule_findings)} location(s))</h3>",
                f'<p class="meta"><span class="status {severity}">{status}</span> · '
                f"Rule: <code>{escape(rule_id)}</code> · [{escape(first.category)}, "
                f"{escape(first.stage)}]</p>",
                f"<p><strong>Why it matters:</strong> {escape(first.message)}</p>",
                f"<p><strong>Suggested action:</strong> {escape(first.replacement)}</p>",
                "<details open><summary>Affected locations</summary><ul>",
            ]
        )
        for finding in rule_findings:
            out.extend(
                [
                    f"<li><code>{escape(f'{finding.file}:{finding.line}')}</code>",
                    f"<pre>{escape(finding.snippet)}</pre>",
                ]
            )
            if finding.detail:
                out.append(f"<strong>Technical context:</strong> {escape(finding.detail)}")
            out.append("</li>")
        out.extend(["</ul></details>", "</article>"])
    out.append("</section>")
    return out
