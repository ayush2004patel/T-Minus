"""Tests for report filenames and operating-system opening behavior."""

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from tminus.report.files import open_report


def test_open_html_passes_a_file_url_to_linux_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HTML reports use an installed browser instead of the file association."""
    opener = Mock()
    monkeypatch.setattr("tminus.report.files.subprocess.Popen", opener)
    monkeypatch.setattr("tminus.report.files.sys.platform", "linux")
    monkeypatch.setattr("tminus.report.files.os.name", "posix")
    monkeypatch.setattr("tminus.report.files.shutil.which", lambda name: "/usr/bin/firefox")
    report = tmp_path / "report.html"
    open_report(report)
    opener.assert_called_once_with(
        ["/usr/bin/firefox", report.as_uri()],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
