"""Turn a ScanResult into text or JSON output."""

from __future__ import annotations

import json
from collections import Counter

from tminus.engine.models import SEVERITY_ORDER, ScanResult

NOT_CHECKED = [  # honest list of what M0 does not cover yet
    "Only Python imports are scanned (rule type: import_path).",
    "JavaScript, Jinja, hooks, site-saved code, data and bench checks are not implemented yet.",
]


def render_text(result: ScanResult, target: str) -> str:
    """Human-readable report grouped by severity, worst first."""
    out = [f"T-MINUS scan -> {target}", f"Files scanned: {result.files_scanned}", ""]
    ordered = sorted(result.findings, key=lambda f: -SEVERITY_ORDER[f.severity])
    for f in ordered:
        out.append(
            f"{f.severity.upper()} {f.file}:{f.line}  {f.rule_id}  [{f.category}, {f.stage}]"
        )
        out.append(f"  {f.snippet}")
        out.append(f"  {f.message}")
        out.append(f"  Fix: {f.replacement}")
        out.append("")
    counts = Counter(f.severity for f in result.findings)
    summary = ", ".join(f"{counts[s]} {s}" for s in ("error", "warning", "info") if counts[s])
    out.append(summary or "No findings.")
    out.append("")
    out.append("Not checked:")
    out.extend(f"  - {line}" for line in NOT_CHECKED)
    out.extend(f"  - skipped {line}" for line in result.skipped)
    return "\n".join(out)


def render_json(result: ScanResult, target: str) -> str:
    """Machine-readable report for CI and later baselines."""
    payload = {"target": target, "result": result.model_dump(mode="json")}
    return json.dumps(payload, indent=2)
