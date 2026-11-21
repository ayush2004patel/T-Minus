"""Tests for baselines and the grouped summary."""

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from tminus.cli.main import app
from tminus.engine.baseline import (
    BaselineError,
    Fingerprint,
    apply_baseline,
    fingerprint,
    load_baseline,
    write_baseline,
)
from tminus.engine.loader import load_rules
from tminus.engine.models import Finding, ScanResult
from tminus.engine.runner import scan_path
from tminus.report.render import render_html, render_json, render_sarif, render_text, summarize

RULES = load_rules("v16")
runner = CliRunner()


def _project(tmp_path: Path, code: str, name: str = "mod.py") -> Path:
    """Create a one-file project and return its folder."""
    (tmp_path / name).write_text(code)
    return tmp_path


def _finding(**changes: Any) -> Finding:
    """A finding with overridable fields."""
    base: dict[str, Any] = {
        "rule_id": "r1",
        "severity": "error",
        "category": "loud",
        "stage": "T-30",
        "file": "a.py",
        "line": 1,
        "snippet": "import imp",
        "message": "m",
        "replacement": "r",
    }
    return Finding(**{**base, **changes})


def test_fingerprint_ignores_the_line_number(tmp_path: Path) -> None:
    """Moving code does not turn an old finding into a new one."""
    assert fingerprint(_finding(line=1), tmp_path) == fingerprint(_finding(line=40), tmp_path)


def test_fingerprint_is_relative_to_the_scan_root(tmp_path: Path) -> None:
    """The same project scanned from two different locations gives the same fingerprint."""
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    assert fingerprint(_finding(file=str(one / "a.py")), one) == fingerprint(
        _finding(file=str(two / "a.py")), two
    )


def test_write_and_load_round_trip(tmp_path: Path) -> None:
    """A saved baseline loads back with the same fingerprints and counts."""
    result = ScanResult(findings=[_finding(), _finding(line=9), _finding(rule_id="r2")])
    path = tmp_path / "baseline.json"
    assert write_baseline(result, tmp_path, path, "v16") == 3
    loaded = load_baseline(path, tmp_path)
    assert loaded[fingerprint(_finding(), tmp_path)] == 2
    assert sum(loaded.values()) == 3


def test_apply_baseline_hides_old_and_keeps_new(tmp_path: Path) -> None:
    """Findings in the baseline are hidden and counted; a new one stays."""
    old = _finding()
    new = _finding(rule_id="r2")
    baseline = load_baseline_from([old], tmp_path)
    result = apply_baseline(ScanResult(findings=[old, new]), baseline, tmp_path)
    assert result.findings == [new]
    assert result.baselined == 1


def load_baseline_from(findings: list[Finding], root: Path) -> Counter[Fingerprint]:
    """Build a baseline from findings through a real file."""
    path = root / "b.json"
    write_baseline(ScanResult(findings=findings), root, path, "v16")
    return load_baseline(path, root)


def test_baseline_is_counted(tmp_path: Path) -> None:
    """If the baseline has one copy and the code now has two, one still shows."""
    same = _finding()
    baseline = load_baseline_from([same], tmp_path)
    both = ScanResult(findings=[same, _finding(line=5)])
    result = apply_baseline(both, baseline, tmp_path)
    assert len(result.findings) == 1
    assert result.baselined == 1


def test_load_accepts_a_json_report(tmp_path: Path) -> None:
    """A report saved with `--format json` can be used as the baseline."""
    project = tmp_path / "p"
    project.mkdir()
    _project(project, "import imp\n")
    report = tmp_path / "report.json"
    report.write_text(render_json(scan_path(project, RULES), "v16"))
    assert sum(load_baseline(report, project).values()) == 1


@pytest.mark.parametrize("content", ["not json", "{}", '{"entries": [{"rule_id": 1}]}', "[]"])
def test_bad_baseline_files(tmp_path: Path, content: str) -> None:
    """Unreadable or wrongly shaped files raise BaselineError."""
    path = tmp_path / "b.json"
    path.write_text(content)
    with pytest.raises(BaselineError):
        load_baseline(path, tmp_path)


def test_missing_baseline_file(tmp_path: Path) -> None:
    """A missing file raises BaselineError."""
    with pytest.raises(BaselineError):
        load_baseline(tmp_path / "nope.json", tmp_path)


def test_cli_write_then_use_a_baseline(tmp_path: Path) -> None:
    """Existing findings are hidden (exit 0); a new finding is reported (exit 1)."""
    project = tmp_path / "proj"
    project.mkdir()
    _project(project, "import imp\n")
    baseline = tmp_path / "baseline.json"
    written = runner.invoke(
        app, ["scan", str(project), "--target", "v16", "--write-baseline", str(baseline)]
    )
    assert written.exit_code == 0
    assert "Wrote a baseline of 1 findings" in written.output

    again = runner.invoke(
        app, ["scan", str(project), "--target", "v16", "--baseline", str(baseline)]
    )
    assert again.exit_code == 0
    assert "No new findings. (1 hidden by the baseline)" in again.output

    _project(project, "import cgi\n", name="other.py")
    new = runner.invoke(app, ["scan", str(project), "--target", "v16", "--baseline", str(baseline)])
    assert new.exit_code == 1
    assert "other.py" in new.output
    assert "mod.py" not in new.output.split("Summary")[0]
    assert "(1 hidden by the baseline)" in new.output


def test_baseline_survives_moving_the_project(tmp_path: Path) -> None:
    """A baseline made in one folder still works on a copy of the project elsewhere."""
    one = tmp_path / "one"
    one.mkdir()
    _project(one, "import imp\n")
    baseline = tmp_path / "b.json"
    runner.invoke(app, ["scan", str(one), "--target", "v16", "--write-baseline", str(baseline)])
    two = tmp_path / "two"
    shutil.copytree(one, two)
    result = runner.invoke(app, ["scan", str(two), "--target", "v16", "--baseline", str(baseline)])
    assert result.exit_code == 0


def test_cli_baseline_errors(tmp_path: Path) -> None:
    """A missing baseline and using both options are usage errors (exit 2)."""
    project = _project(tmp_path, "import json\n")
    missing = runner.invoke(
        app, ["scan", str(project), "--target", "v16", "--baseline", str(tmp_path / "x.json")]
    )
    assert missing.exit_code == 2
    both = runner.invoke(
        app,
        [
            "scan",
            str(project),
            "--target",
            "v16",
            "--baseline",
            "a.json",
            "--write-baseline",
            "b.json",
        ],
    )
    assert both.exit_code == 2


def test_summary_groups_by_stage_severity_and_category() -> None:
    """The summary counts findings by stage (with severities) and by category."""
    result = ScanResult(
        findings=[
            _finding(),
            _finding(category="quiet", severity="warning"),
            _finding(category="quiet", stage="T-14"),
        ],
        baselined=2,
    )
    summary = summarize(result)
    assert summary["total"] == 3
    assert summary["by_stage"] == {"T-30": {"error": 1, "warning": 1}, "T-14": {"error": 1}}
    assert list(summary["by_stage"]) == ["T-30", "T-14"]  # earliest stage first
    assert summary["by_category"] == {"loud": 1, "quiet": 2}
    assert summary["baselined"] == 2


def test_text_report_shows_the_grouped_summary() -> None:
    """The text report ends with severity, stage and category lines."""
    result = ScanResult(findings=[_finding(), _finding(category="quiet", severity="warning")])
    text = render_text(result, "v16")
    assert "Summary: 1 error, 1 warning" in text
    assert "by stage:    T-30: 1 error, 1 warning" in text
    assert "by category: 1 loud, 1 quiet" in text


def test_text_report_groups_by_rule_and_keeps_technical_evidence() -> None:
    """The text report makes a rule one checklist while preserving every location."""
    result = ScanResult(
        findings=[
            _finding(file="api.py", line=7, detail="called by hooks.py"),
            _finding(file="web.py", line=12),
            _finding(file="web.py", line=18, rule_id="r2", severity="warning", category="quiet"),
        ]
    )
    text = render_text(result, "v16", app_name="my_app")
    assert "T-MINUS scan report" in text
    assert "Application: my_app" in text
    assert "Result: ACTION REQUIRED" in text
    assert "What to do next:" in text
    assert "Errors (2)" in text
    assert "r1 (2 location(s))" in text
    assert "Status: ACTION REQUIRED • Rule: r1 • [loud, T-30]" in text
    assert "api.py:7" in text
    assert "web.py:12" in text
    assert "Code: import imp" in text
    assert "Why it matters: m" in text
    assert "Technical context: called by hooks.py" in text
    assert "Suggested action: r" in text
    assert "Warnings (1)" in text


def test_text_report_coloring_is_opt_in() -> None:
    """ANSI colors are present only when terminal color is explicitly requested."""
    result = ScanResult(findings=[_finding()])
    assert "\033[" not in render_text(result, "v16")
    assert "\033[" in render_text(result, "v16", color=True)


def test_html_report_is_self_contained_and_escapes_finding_text() -> None:
    """The HTML report groups a rule and escapes source code safely."""
    result = ScanResult(findings=[_finding(snippet="value < other", detail="a & b")])
    report = render_html(result, "v16", app_name="my_app")
    assert report.startswith("<!doctype html>")
    assert "<style>" in report
    assert "Application:</strong> my_app" in report
    assert "Rule: <code>r1</code>" in report
    assert "value &lt; other" in report
    assert "a &amp; b" in report


def test_json_report_has_summary_and_baselined_count(tmp_path: Path) -> None:
    """The JSON report carries the summary and how many findings were hidden."""
    project = _project(tmp_path, "import imp\n")
    data = json.loads(render_json(scan_path(project, RULES), "v16"))
    assert data["summary"]["total"] == 1
    assert data["result"]["baselined"] == 0


def test_sarif_report_keeps_rule_location_and_technical_details(tmp_path: Path) -> None:
    """SARIF output has standard rule metadata and a clickable source location."""
    project = _project(tmp_path, "import imp\n")
    data = json.loads(render_sarif(scan_path(project, RULES), "v16", RULES, project))
    run = data["runs"][0]
    result = run["results"][0]
    rule = next(item for item in run["tool"]["driver"]["rules"] if item["id"] == result["ruleId"])
    assert data["version"] == "2.1.0"
    assert result["ruleId"] == "v16-removed-python-stdlib"
    assert result["level"] == "error"
    assert result["locations"][0]["physicalLocation"]["artifactLocation"] == {
        "uri": "mod.py",
        "uriBaseId": "SRCROOT",
    }
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 1
    assert result["properties"]["suggestedAction"]
    assert rule["shortDescription"]["text"]
    assert rule["properties"]["references"]
