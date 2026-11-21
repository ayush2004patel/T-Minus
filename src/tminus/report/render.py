"""Turn a ScanResult into text or JSON output."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
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
