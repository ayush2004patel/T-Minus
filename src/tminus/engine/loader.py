"""Load and validate YAML rule files for a target version."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from tminus.engine.models import Rule

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"  # rules ship inside the package


class RuleLoadError(Exception):
    """A rule file is invalid."""


class UnknownTargetError(RuleLoadError):
    """No rule folder exists for the requested target."""


def load_rules(target: str, rules_dir: Path | None = None) -> list[Rule]:
    """Load every rule for a target, checking id and target match the file location."""
    folder = (rules_dir or RULES_DIR) / target
    if not folder.is_dir():
        raise UnknownTargetError(f"unknown target: {target}")

    rules: list[Rule] = []
    for path in sorted(folder.glob("*.yaml")):  # top level only, so _candidates/ is ignored
        if path.name == "target.yaml":  # metadata file, not a rule
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            rule = Rule.model_validate(data)
        except (yaml.YAMLError, ValidationError) as exc:
            raise RuleLoadError(f"{path.name}: {exc}") from exc
        if rule.id != path.stem:
            raise RuleLoadError(f"{path.name}: rule id '{rule.id}' must equal the file name")
        if rule.target != target:
            raise RuleLoadError(f"{path.name}: target '{rule.target}' is not '{target}'")
        rules.append(rule)
    return rules
