"""Data models for rules, findings and scan results."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Severity = Literal["error", "warning", "info"]
Category = Literal["data", "loud", "quiet", "silent"]  # the four failure classes
Stage = Literal["T-30", "T-14", "T-7", "T-3", "T-1", "T-0"]
FixTiming = Literal["before", "with-upgrade"]
Autofix = Literal["none", "safe", "review"]
Confidence = Literal["high", "medium", "low"]

SEVERITY_ORDER: dict[str, int] = {"info": 0, "warning": 1, "error": 2}  # higher = worse


class StrictModel(BaseModel):
    """Base model that rejects unknown keys, so typos in rule files fail loudly."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ImportPathMatch(StrictModel):
    """Match imports of the listed top-level modules."""

    type: Literal["import_path"]
    modules: list[str] = Field(min_length=1)


class HookFunctionMatch(StrictModel):
    """Check the functions named in a hooks.py table such as has_permission."""

    type: Literal["hook_function"]
    hook: str
    check: Literal["returns_none", "unreadable"]


class HookClassMatch(StrictModel):
    """Check the classes named in a hooks.py table such as override_doctype_class."""

    type: Literal["hook_class"]
    hook: str
    check: Literal["no_base", "unreadable"]


class CallMatch(StrictModel):
    """Check uses of functions given by full dotted path (removed or changed signature)."""

    type: Literal["call"]
    paths: list[str] = Field(min_length=1)  # every import path that reaches the function
    check: Literal["removed", "keyword_only", "positional_count", "first_arg_named"]
    count: int | None = None  # positional_count: flag calls with exactly this many arguments
    names: list[str] = Field(default_factory=list)  # first_arg_named: old parameter names

    @model_validator(mode="after")
    def _check_extra_fields(self) -> Self:
        """Make sure each check comes with the extra field it needs."""
        if self.check == "positional_count" and self.count is None:
            raise ValueError("positional_count needs `count`")
        if self.check == "first_arg_named" and not self.names:
            raise ValueError("first_arg_named needs `names`")
        return self


class DoctypeFieldMatch(StrictModel):
    """Fields that were removed or renamed, per DocType, with a note on what replaced them."""

    type: Literal["doctype_field"]
    doctypes: dict[str, dict[str, str]] = Field(min_length=1)  # doctype -> {field -> note}


class DoctypeNameMatch(StrictModel):
    """DocTypes that were removed, with a note on what replaced them."""

    type: Literal["doctype_name"]
    names: dict[str, str] = Field(min_length=1)  # doctype -> note


class PackageMatch(StrictModel):
    """Checks on an app's packaging files (pyproject.toml, setup.py, requirements.txt, ...)."""

    type: Literal["package"]
    check: Literal[
        "requires_python", "frappe_bound", "frappe_bound_missing", "node_engine", "dependency_pins"
    ]
    versions: list[str] = Field(default_factory=list)  # flag when the app's range rejects all
    pins: dict[str, str] = Field(default_factory=dict)  # dependency_pins: name -> frappe's pin

    @model_validator(mode="after")
    def _check_extra_fields(self) -> Self:
        """Make sure each check comes with the data it needs."""
        needs_versions = {"requires_python", "frappe_bound", "node_engine"}
        if self.check in needs_versions and not self.versions:
            raise ValueError(f"{self.check} needs `versions`")
        if self.check == "dependency_pins" and not self.pins:
            raise ValueError("dependency_pins needs `pins`")
        return self


# All match types; the `type` key decides which model validates the YAML.
Match = Annotated[
    ImportPathMatch
    | HookFunctionMatch
    | HookClassMatch
    | CallMatch
    | DoctypeFieldMatch
    | DoctypeNameMatch
    | PackageMatch,
    Field(discriminator="type"),
]


class RequirementSpec(StrictModel):
    """One environment requirement of a target version (Python, Node, MariaDB, Redis)."""

    minimum: str
    below: str | None = None  # exclusive upper bound, e.g. Python < 3.15
    recommended: str | None = None
    source: str = ""


class TargetInfo(StrictModel):
    """Contents of rules/<target>/target.yaml."""

    target: str
    checked_on: date | None = None
    note: str = ""
    requirements: dict[str, RequirementSpec] = Field(default_factory=dict)


class Rule(StrictModel):
    """One breaking change, loaded from one YAML file."""

    id: str
    title: str
    target: str
    app: str
    severity: Severity
    category: Category
    stage: Stage
    match: Match
    message: str
    replacement: str
    fix: FixTiming
    autofix: Autofix = "none"
    confidence: Confidence = "high"
    references: list[str] = Field(default_factory=list)


class Hit(StrictModel):
    """One place a matcher found: a line number and optional extra context."""

    line: int
    detail: str = ""


class Finding(StrictModel):
    """One place in the scanned code that a rule matched."""

    rule_id: str
    severity: Severity
    category: Category
    stage: Stage
    file: str
    line: int
    snippet: str
    message: str
    replacement: str
    detail: str = ""  # extra context, e.g. which hook points at this code

    @classmethod
    def from_rule(cls, rule: Rule, file: str, line: int, snippet: str, detail: str = "") -> Finding:
        """Build a finding from a rule and a code location."""
        return cls(
            rule_id=rule.id,
            severity=rule.severity,
            category=rule.category,
            stage=rule.stage,
            file=file,
            line=line,
            snippet=snippet.strip(),
            message=rule.message.strip(),
            replacement=rule.replacement.strip(),
            detail=detail,
        )


class ScanResult(StrictModel):
    """Everything a scan produced, including what it could not check."""

    findings: list[Finding] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)  # "file: reason" lines
    files_scanned: int = 0
