"""Tests for the version-range helpers."""

import pytest

from tminus.engine.versions import node_allows, spec_allows, specs_conflict


def test_spec_allows() -> None:
    """A PEP 440 range allows or rejects a version; garbage is unreadable."""
    assert spec_allows(">=3.14,<3.15", "3.14") is True
    assert spec_allows(">=3.10,<3.13", "3.14") is False
    assert spec_allows(">=3.10", "3.14") is True
    assert spec_allows("not a spec", "3.14") is None


@pytest.mark.parametrize(
    ("app", "frappe", "expected"),
    [
        ("<3", "==3.1.9", True),  # app caps below frappe's exact pin
        ("<2.30", "~=2.32.0", True),
        (">=9", "~=13.0.0", False),  # open range overlaps
        (">=2,<3", "~=2.18.0", False),
        ("==1.1.1", "==1.1.2", True),  # two different exact pins
        ("~=22.3.5", "~=24.6.1", True),
        (">2.18.0", "~=2.18.0", False),  # exclusive lower bound still leaves room
        ("", "==3.1.9", False),  # no restriction at all
    ],
)
def test_specs_conflict(app: str, frappe: str, expected: bool) -> None:
    """Two ranges conflict when no version satisfies both."""
    assert specs_conflict(app, frappe) is expected


def test_specs_conflict_unreadable() -> None:
    """An unreadable specifier gives no verdict."""
    assert specs_conflict("???", "==1.0") is None


@pytest.mark.parametrize(
    ("range_text", "expected"),
    [
        (">=18", True),
        (">=24", True),
        ("<=20", False),
        ("<25", True),
        ("<24", False),
        (">24", False),  # 24 itself is not above 24
        (">23", True),
        ("^20", False),
        ("^24", True),
        ("~24", True),
        ("~24.1", False),  # means >=24.1.0 <24.2.0, so 24.0.0 is outside
        ("24.x", True),
        ("20.x", False),
        ("24", True),
        ("18 || 20 || >=24", True),
        ("18 || 20", False),
        (">=18 <22", False),
        (">= 18", True),
        ("*", True),
    ],
)
def test_node_allows(range_text: str, expected: bool) -> None:
    """npm-style ranges are checked against Node 24."""
    assert node_allows(range_text, "24") is expected


def test_node_allows_unsupported_syntax() -> None:
    """Hyphen ranges and nonsense give no verdict instead of a guess."""
    assert node_allows("14 - 20", "24") is None
    assert node_allows("lts/*", "24") is None
