"""Write reports to disk and open them with the system default application."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


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
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])  # noqa: S603, S607
    elif os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", str(path)])  # noqa: S603, S607
