"""Walk a path and run the scanners over every Python file."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from tminus.engine.models import Finding, Rule, ScanResult
from tminus.engine.scanners.python_ast import scan_source

SKIP_DIRS = {".git", "node_modules", "env", ".venv", "venv", "__pycache__", "dist", "build"}


def iter_python_files(root: Path) -> Iterator[Path]:
    """Yield .py files under root, skipping build and environment folders."""
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*.py")):
        if not SKIP_DIRS.intersection(path.relative_to(root).parts):
            yield path


def scan_path(root: Path, rules: list[Rule]) -> ScanResult:
    """Scan a file or folder; files that cannot be read or parsed are listed as skipped."""
    if not root.exists():
        raise FileNotFoundError(str(root))
    findings: list[Finding] = []
    skipped: list[str] = []
    count = 0
    for path in iter_python_files(root):
        try:
            source = path.read_text(encoding="utf-8")
            findings.extend(scan_source(source, str(path), rules))
            count += 1
        except (UnicodeDecodeError, OSError) as exc:  # unreadable file
            skipped.append(f"{path}: cannot read ({exc.__class__.__name__})")
        except SyntaxError as exc:  # not valid Python for this interpreter
            skipped.append(f"{path}: syntax error at line {exc.lineno}")
    return ScanResult(findings=findings, skipped=skipped, files_scanned=count)
