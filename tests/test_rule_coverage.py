"""Every rule needs a violation fixture; the clean fixtures must stay clean."""

from pathlib import Path

from tminus.engine.loader import load_rules
from tminus.engine.runner import scan_path

FIXTURES = Path(__file__).parent / "fixtures"


def test_every_rule_has_a_violation_fixture() -> None:
    """Fails when a rule is added without a fixture line or fixture app that triggers it."""
    rules = load_rules("v16")
    hit: set[str] = set()
    for fixture in ("violations.py", "app_bad", "overrides_bad", "pkg_bad", "pkg_nobound"):
        hit |= {f.rule_id for f in scan_path(FIXTURES / fixture, rules).findings}
    assert {r.id for r in rules} - hit == set()


def test_clean_fixtures_have_no_findings() -> None:
    """Guarded, suppressed and correct code must not be flagged."""
    rules = load_rules("v16")
    for fixture in ("clean.py", "app_clean", "overrides_clean", "pkg_clean"):
        assert scan_path(FIXTURES / fixture, rules).findings == [], fixture
