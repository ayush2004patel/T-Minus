"""Data models for rules, findings and scan results."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

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


# All match types; the `type` key decides which model validates the YAML.
Match = Annotated[ImportPathMatch | HookFunctionMatch, Field(discriminator="type")]


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
