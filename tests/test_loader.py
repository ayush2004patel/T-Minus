"""Tests for rule loading and validation."""

from pathlib import Path

import pytest

from tminus.engine.loader import RuleLoadError, UnknownTargetError, load_rules

GOOD = """
id: {id}
title: t
target: v16
app: frappe
severity: error
category: loud
stage: T-30
match: {{type: import_path, modules: [imp]}}
message: m
replacement: r
fix: before
{extra}
"""


def _write(folder: Path, name: str, extra: str = "", rule_id: str | None = None) -> None:
    """Write one rule file into a temporary v16 folder."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.yaml").write_text(GOOD.format(id=rule_id or name, extra=extra))


def test_real_rules_load() -> None:
    """The shipped v16 rules load and are non-empty."""
    rules = load_rules("v16")
    assert rules
    assert all(r.target == "v16" for r in rules)


def test_unknown_target() -> None:
    """A target without a folder raises UnknownTargetError."""
    with pytest.raises(UnknownTargetError):
        load_rules("v99")


def test_unknown_key_rejected(tmp_path: Path) -> None:
    """A misspelled key in a rule file is an error, not silently ignored."""
    _write(tmp_path / "v16", "r1", extra="severty: error")
    with pytest.raises(RuleLoadError):
        load_rules("v16", tmp_path)


def test_id_must_match_filename(tmp_path: Path) -> None:
    """Rule id and file name must agree."""
    _write(tmp_path / "v16", "r1", rule_id="other")
    with pytest.raises(RuleLoadError):
        load_rules("v16", tmp_path)


def test_target_yaml_is_not_a_rule(tmp_path: Path) -> None:
    """target.yaml is metadata and must not be parsed as a rule."""
    _write(tmp_path / "v16", "r1")
    (tmp_path / "v16" / "target.yaml").write_text("target: v16\n")
    assert [r.id for r in load_rules("v16", tmp_path)] == ["r1"]


def test_positional_count_needs_count(tmp_path: Path) -> None:
    """A call rule using positional_count without `count` is rejected."""
    folder = tmp_path / "v16"
    folder.mkdir()
    (folder / "r1.yaml").write_text(
        GOOD.format(id="r1", extra="").replace(
            "match: {type: import_path, modules: [imp]}",
            "match: {type: call, check: positional_count, paths: [a.b]}",
        )
    )
    with pytest.raises(RuleLoadError):
        load_rules("v16", tmp_path)
