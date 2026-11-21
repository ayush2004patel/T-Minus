"""Tests for report filenames and operating-system opening behavior."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from tminus.report.files import open_report


def test_open_html_passes_a_file_url_to_linux_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Browsers receive an unambiguous local URL for self-contained HTML reports."""
    opener = Mock()
    monkeypatch.setattr("tminus.report.files.subprocess.Popen", opener)
    monkeypatch.setattr("tminus.report.files.sys.platform", "linux")
    monkeypatch.setattr("tminus.report.files.os.name", "posix")
    report = tmp_path / "report.html"
    open_report(report)
    opener.assert_called_once_with(["xdg-open", report.as_uri()])
