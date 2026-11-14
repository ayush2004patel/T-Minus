"""Turn a ScanResult into text or JSON output."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from tminus.engine.models import SEVERITY_ORDER, ScanResult

NOT_CHECKED = [  # honest list of what is not covered yet
    "Static checks only: Python, JavaScript, Print Format templates, hooks, SQL text, packaging.",
    "Not implemented yet: site data, site-saved code, migrate rehearsal, v15 vs v16 comparison.",
]

STAGE_ORDER = ["T-30", "T-14", "T-7", "T-3", "T-1", "T-0"]  # the countdown, earliest first
SEVERITIES = ("error", "warning", "info")


def _counts_text(counts: Counter[str], keys: tuple[str, ...]) -> str:
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


def render_text(result: ScanResult, target: str) -> str:
    """Human-readable report grouped by severity, worst first."""
    out = [f"T-MINUS scan -> {target}", f"Files scanned: {result.files_scanned}", ""]
    ordered = sorted(result.findings, key=lambda f: -SEVERITY_ORDER[f.severity])
    for f in ordered:
        out.append(
            f"{f.severity.upper()} {f.file}:{f.line}  {f.rule_id}  [{f.category}, {f.stage}]"
        )
        out.append(f"  {f.snippet}")
        if f.detail:
            out.append(f"  {f.detail}")
        out.append(f"  {f.message}")
        out.append(f"  Fix: {f.replacement}")
        out.append("")
    out.extend(_summary_lines(result))
    out.append("")
    out.append("Not checked:")
    out.extend(f"  - {line}" for line in NOT_CHECKED)
    out.extend(f"  - skipped {line}" for line in result.skipped)
    return "\n".join(out)


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
