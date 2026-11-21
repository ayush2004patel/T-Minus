"""Write reports to disk and open them with the system default application."""

from __future__ import annotations

import os
import shutil
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
        subprocess.Popen(  # noqa: S603, S607
            ["open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    elif os.name == "nt":
        os.startfile(target)  # type: ignore[attr-defined]  # noqa: S606
    else:
        command = (
            _linux_html_command(target) if path.suffix.lower() == ".html" else ["xdg-open", target]
        )
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603


def _linux_html_command(url: str) -> list[str]:
    """Prefer an installed browser over an HTML file association on Linux."""
    browsers = ("firefox", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
    for browser in browsers:
        if executable := shutil.which(browser):
            return [executable, url]
    return ["xdg-open", url]
