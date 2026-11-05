"""Walk a path and run the scanners over it."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from tminus.engine.models import Finding, Rule, ScanResult
from tminus.engine.paths import is_skipped
from tminus.engine.scanners.hooks import scan_hooks
from tminus.engine.scanners.js_ast import scan_js
from tminus.engine.scanners.print_format import scan_print_formats
from tminus.engine.scanners.python_ast import scan_source


def iter_python_files(root: Path) -> Iterator[Path]:
    """Yield .py files under root, skipping build and environment folders."""
    if root.is_file():
        if root.suffix == ".py":
            yield root
        return
    for path in sorted(root.rglob("*.py")):
        if not is_skipped(root, path):
            yield path


def iter_js_files(root: Path) -> Iterator[Path]:
    """Yield .js files under root, skipping build folders and minified/bundled files."""
    candidates = [root] if root.is_file() else sorted(root.rglob("*.js"))
    for path in candidates:
        if path.suffix != ".js" or path.name.endswith((".min.js", ".bundle.js")):
            continue
        if root.is_file() or not is_skipped(root, path):
            yield path


def scan_path(root: Path, rules: list[Rule]) -> ScanResult:
    """Scan a file or folder; files that cannot be read or parsed are listed as skipped."""
    if not root.exists():
        raise FileNotFoundError(str(root))
    findings: list[Finding] = []
    skipped: list[str] = []
    count = 0
    for path in iter_python_files(root):  # pass 1: per-file rules
        try:
            source = path.read_text(encoding="utf-8")
            findings.extend(scan_source(source, str(path), rules))
            count += 1
        except (UnicodeDecodeError, OSError) as exc:  # unreadable file
            skipped.append(f"{path}: cannot read ({exc.__class__.__name__})")
        except SyntaxError as exc:  # not valid Python for this interpreter
            skipped.append(f"{path}: syntax error at line {exc.lineno}")
    hook_findings, hook_notes = scan_hooks(root, rules)  # pass 2: app-level hook rules
    findings.extend(hook_findings)
    skipped.extend(hook_notes)

    for js_path in iter_js_files(root):  # pass 3: client-side JavaScript
        try:
            js_findings, has_errors = scan_js(js_path.read_bytes(), str(js_path), rules)
        except OSError as exc:
            skipped.append(f"{js_path}: cannot read ({exc.__class__.__name__})")
            continue
        findings.extend(js_findings)
        count += 1
        if has_errors:  # tree-sitter still returns a partial tree
            skipped.append(f"{js_path}: JavaScript syntax errors, only partly checked")

    pf_findings, pf_notes, pf_count = scan_print_formats(root, rules)  # pass 4: print formats
    findings.extend(pf_findings)
    skipped.extend(pf_notes)
    return ScanResult(findings=findings, skipped=skipped, files_scanned=count + pf_count)
