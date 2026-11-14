"""Baselines: remember today's findings so that only new ones are reported."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from tminus.engine.models import Finding, ScanResult

BASELINE_VERSION = 1
Fingerprint = tuple[
    str, str, str, str
]  # (rule id, file relative to the scan root, snippet, detail)


class BaselineError(Exception):
    """The baseline file cannot be read or has the wrong shape."""


def _relative(file: str, root: Path) -> str:
    """The file path relative to the scanned folder, with forward slashes."""
    base = root if root.is_dir() else root.parent
    try:
        return Path(os.path.relpath(file, base)).as_posix()
    except ValueError:  # a different drive on Windows
        return Path(file).as_posix()


def fingerprint(finding: Finding, root: Path) -> Fingerprint:
    """Identify a finding without its line number, so edits above it do not make it "new"."""
    return (finding.rule_id, _relative(finding.file, root), finding.snippet.strip(), finding.detail)


def write_baseline(result: ScanResult, root: Path, path: Path, target: str) -> int:
    """Save the current findings as a baseline file; returns how many findings it holds."""
    counts = Counter(fingerprint(f, root) for f in result.findings)
    entries = [
        {"rule_id": rule, "file": file, "snippet": snippet, "detail": detail, "count": count}
        for (rule, file, snippet, detail), count in sorted(counts.items())
    ]
    document = {"version": BASELINE_VERSION, "target": target, "entries": entries}
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return len(result.findings)


def _from_entries(entries: list[dict[str, Any]]) -> Counter[Fingerprint]:
    """Fingerprints from a baseline file's entries (each with a count)."""
    counts: Counter[Fingerprint] = Counter()
    for entry in entries:
        key = (entry["rule_id"], entry["file"], entry["snippet"], entry.get("detail", ""))
        counts[key] += int(entry.get("count", 1))
    return counts


def load_baseline(path: Path, root: Path) -> Counter[Fingerprint]:
    """Read a baseline file, or a full JSON report saved with `--format json`."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "entries" in data:
            return _from_entries(data["entries"])
        if "result" in data:  # a JSON report: use its findings
            findings = [Finding.model_validate(f) for f in data["result"]["findings"]]
            return Counter(fingerprint(f, root) for f in findings)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BaselineError(f"cannot read baseline {path}: {exc}") from exc
    raise BaselineError(f"{path} is not a T-MINUS baseline or JSON report")


def apply_baseline(result: ScanResult, baseline: Counter[Fingerprint], root: Path) -> ScanResult:
    """Hide the findings that are in the baseline (counted, so a second copy still shows)."""
    remaining = Counter(baseline)
    kept: list[Finding] = []
    hidden = 0
    for finding in result.findings:
        key = fingerprint(finding, root)
        if remaining[key] > 0:
            remaining[key] -= 1
            hidden += 1
        else:
            kept.append(finding)
    return result.model_copy(update={"findings": kept, "baselined": hidden})
