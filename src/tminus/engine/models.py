"""Data models for rules, findings and scan results."""

from __future__ import annotations

from typing import Literal

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


# More match types join this as a union later (call, hook_key, ...).
Match = ImportPathMatch


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


class ScanResult(StrictModel):
    """Everything a scan produced, including what it could not check."""

    findings: list[Finding] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)  # "file: reason" lines
    files_scanned: int = 0
