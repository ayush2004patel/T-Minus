"""Compare the versions installed on this machine with what a target version needs."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from packaging.version import InvalidVersion, Version

from tminus.engine.models import RequirementSpec

Runner = Callable[[list[str]], str | None]  # runs a command, returns its output or None
Status = Literal["ok", "upgrade", "missing"]

_VERSION = r"(\d+\.\d+(?:\.\d+)?)"
_PATTERNS: dict[str, list[str]] = {
    "python": [rf"Python\s+{_VERSION}"],
    "node": [rf"v?{_VERSION}"],
    "redis": [rf"v={_VERSION}"],
    "mariadb": [rf"{_VERSION}-MariaDB", rf"Distrib\s+{_VERSION}"],
}
_COMMANDS: dict[str, list[list[str]]] = {
    "python": [["python3", "--version"]],
    "node": [["node", "--version"]],
    "redis": [["redis-server", "--version"]],
    "mariadb": [["mariadb", "--version"], ["mysql", "--version"]],
}
_PYVENV = re.compile(rf"^version(?:_info)?\s*=\s*{_VERSION}", re.MULTILINE)


@dataclass(frozen=True)
class EnvRow:
    """One line of the environment report."""

    name: str
    found: str | None
    where: str  # how it was found (a command or the bench's pyvenv.cfg)
    needs: str
    status: Status
    note: str = ""


def run_command(args: list[str]) -> str | None:
    """Run a command; return its output, or None if it is missing, fails or hangs."""
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (done.stdout + done.stderr).strip() or None


def _first_version(text: str, patterns: list[str]) -> str | None:
    """The first version number matched by any of the patterns."""
    for pattern in patterns:
        if match := re.search(pattern, text):
            return match.group(1)
    return None


def detect(name: str, run: Runner, bench: Path | None) -> tuple[str | None, str]:
    """(version, how it was found) of one tool on this machine."""
    if name == "python" and bench is not None:  # the bench's own interpreter, without running it
        cfg = bench / "env" / "pyvenv.cfg"
        if cfg.is_file():
            match = _PYVENV.search(cfg.read_text(encoding="utf-8"))
            if match:
                return match.group(1), f"{cfg}"
    for command in _COMMANDS.get(name, []):
        output = run(command)
        if output and (version := _first_version(output, _PATTERNS[name])):
            return version, " ".join(command)
    return None, ""


def needs_text(spec: RequirementSpec) -> str:
    """The requirement as short text: `>=3.14,<3.15`, `>=10.6 (11.8 recommended)`."""
    text = f">={spec.minimum}" + (f",<{spec.below}" if spec.below else "")
    return text + (f" ({spec.recommended} recommended)" if spec.recommended else "")


def _at_least(found: str, wanted: str) -> bool | None:
    """True if `found` is the same as or newer than `wanted` (None if unreadable)."""
    try:
        return Version(found) >= Version(wanted)
    except InvalidVersion:
        return None


def judge(found: str | None, spec: RequirementSpec) -> tuple[Status, str]:
    """Status and an optional note for one detected version."""
    if found is None:
        return "missing", "not found on this machine"
    if _at_least(found, spec.minimum) is not True:
        return "upgrade", f"older than {spec.minimum}"
    if spec.below and _at_least(found, spec.below) is True:
        return "upgrade", f"{spec.below} or newer is not supported"
    if spec.recommended and _at_least(found, spec.recommended) is False:
        return "ok", f"works, but {spec.recommended} is recommended"
    return "ok", ""


def check_environment(
    requirements: dict[str, RequirementSpec], run: Runner, bench: Path | None
) -> list[EnvRow]:
    """Detect each required tool on this machine and compare it with the target's needs."""
    rows: list[EnvRow] = []
    for name, spec in requirements.items():
        found, where = detect(name, run, bench)
        status, note = judge(found, spec)
        rows.append(EnvRow(name, found, where, needs_text(spec), status, note))
    return rows


_LABELS = {"ok": "ok", "upgrade": "UPGRADE NEEDED", "missing": "NOT FOUND"}


def format_rows(rows: list[EnvRow], target: str) -> str:
    """Human-readable environment report."""
    out = [f"T-MINUS environment -> {target}", ""]
    for row in rows:
        found = row.found or "-"
        line = f"  {row.name:<8} found {found:<9} needs {row.needs:<26} {_LABELS[row.status]}"
        out.append(line + (f"  ({row.note})" if row.note else ""))
    out += [
        "",
        "These are the versions on this machine. A v16 bench needs the versions in the",
        "'needs' column; build it as a NEW bench and keep this one as the rollback.",
    ]
    return "\n".join(out)
