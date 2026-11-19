"""Path rules shared by all scanners."""

from __future__ import annotations

from pathlib import Path

UPSTREAM_APPS = {"frappe", "erpnext", "hrms"}  # installed from their own version-16 branch
SKIP_DIRS = {".git", "node_modules", "env", ".venv", "venv", "__pycache__", "dist", "build"}


def is_skipped(root: Path, path: Path) -> bool:
    """True if the path lies inside a skipped folder such as node_modules."""
    return bool(SKIP_DIRS.intersection(path.relative_to(root).parts))
