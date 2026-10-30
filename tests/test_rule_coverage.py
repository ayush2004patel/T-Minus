"""Every rule needs a violation fixture; the clean fixture must stay clean."""

from pathlib import Path

from tminus.engine.loader import load_rules
from tminus.engine.scanners.python_ast import scan_source

FIXTURES = Path(__file__).parent / "fixtures"


def test_every_rule_has_a_violation_fixture() -> None:
    """Fails when a rule is added without a line in violations.py that triggers it."""
    rules = load_rules("v16")
    source = (FIXTURES / "violations.py").read_text()
    hit = {f.rule_id for f in scan_source(source, "violations.py", rules)}
    assert {r.id for r in rules} - hit == set()


def test_clean_fixture_has_no_findings() -> None:
    """Guarded and suppressed imports in clean.py must not be flagged."""
    rules = load_rules("v16")
    source = (FIXTURES / "clean.py").read_text()
    assert scan_source(source, "clean.py", rules) == []
