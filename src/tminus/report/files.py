"""Write reports to disk and open them with the system default application."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def default_report_path(app_path: Path, target: str, fmt: str) -> Path:
    """Return the Downloads-folder filename for a saved report."""
    app_name = app_path.name if app_path.is_dir() else app_path.stem
    safe_name = "".join(char if char.isalnum() or char in "-_." else "-" for char in app_name)
    return Path.home() / "Downloads" / f"{safe_name}-tminus-{target}-report.{fmt}"


def write_report(path: Path, content: str | bytes) -> Path:
    """Write one report and return its absolute path."""
    resolved = path.resolve()
    if isinstance(content, bytes):
        resolved.write_bytes(content)
    else:
        resolved.write_text(content, encoding="utf-8")
    return resolved


def open_report(path: Path) -> None:
    """Open a saved HTML or PDF report using the operating system default."""
    target = path.as_uri() if path.suffix.lower() == ".html" else str(path)
    if sys.platform == "darwin":
        subprocess.Popen(["open", target])  # noqa: S603, S607
    elif os.name == "nt":
        os.startfile(target)  # type: ignore[attr-defined]  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", target])  # noqa: S603, S607
