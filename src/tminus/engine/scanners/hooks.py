"""App-level scanner: read hooks.py tables and check the functions they name."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from tminus.engine.matchers.returns_none import FunctionNode, can_return_none
from tminus.engine.models import Finding, HookFunctionMatch, Rule
from tminus.engine.paths import is_skipped
from tminus.engine.suppress import ignored_ids

ParseCache = dict[Path, tuple[list[str], ast.Module] | None]


class NotLiteralError(Exception):
    """A hook table is built at run time, so it cannot be read statically."""


@dataclass(frozen=True)
class HookEntry:
    """One `DocType -> dotted function path` pair from a hooks.py table."""

    key: str
    dotted: str
    line: int


@dataclass(frozen=True)
class LocatedFunction:
    """A hook target found in the app's own source."""

    file: Path
    lines: list[str]
    func: FunctionNode


def find_hooks_files(root: Path) -> Iterator[Path]:
    """Yield every hooks.py under root (or root itself if it is a hooks.py)."""
    if root.is_file():
        if root.name == "hooks.py":
            yield root
        return
    for path in sorted(root.rglob("hooks.py")):
        if not is_skipped(root, path):
            yield path


def _paths(value: ast.expr) -> list[str]:
    """Dotted paths from a string, or from a list/tuple of strings."""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return [value.value]
    if isinstance(value, ast.List | ast.Tuple):
        out: list[str] = []
        for item in value.elts:
            if not (isinstance(item, ast.Constant) and isinstance(item.value, str)):
                raise NotLiteralError
            out.append(item.value)
        return out
    raise NotLiteralError


def read_hook_entries(tree: ast.Module, hook: str) -> list[HookEntry]:
    """Entries of `hook = {...}` in hooks.py; empty if the hook is not set."""
    entries: list[HookEntry] = []
    for node in tree.body:
        is_target = isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == hook for t in node.targets
        )
        if not (is_target and isinstance(node, ast.Assign)):
            continue
        if not isinstance(node.value, ast.Dict):  # e.g. built by a function call
            raise NotLiteralError
        for key, value in zip(node.value.keys, node.value.values, strict=True):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                raise NotLiteralError  # also catches **spread (key is None)
            entries.extend(HookEntry(key.value, p, value.lineno) for p in _paths(value))
    return entries


def _parse(path: Path, cache: ParseCache) -> tuple[list[str], ast.Module] | None:
    """Parse a file once and remember the result; None if it cannot be read."""
    if path not in cache:
        try:
            text = path.read_text(encoding="utf-8")
            cache[path] = (text.splitlines(), ast.parse(text, filename=str(path)))
        except (OSError, UnicodeDecodeError, SyntaxError):
            cache[path] = None
    return cache[path]


def _find_function(tree: ast.Module, name: str) -> FunctionNode | None:
    """Find a top-level function by name."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
    return None


def _locate(pkg_dir: Path, dotted: str, cache: ParseCache) -> LocatedFunction | None:
    """Resolve `app.module.func` to a function in this app's own source, else None."""
    parts = dotted.split(".")
    if len(parts) < 2 or parts[0] != pkg_dir.name:  # points outside this app
        return None
    module_parts, func_name = parts[1:-1], parts[-1]
    base = pkg_dir.joinpath(*module_parts)
    candidates = [base / "__init__.py"]
    if module_parts:
        candidates.insert(0, base.with_suffix(".py"))  # module file wins over package
    for path in candidates:
        if not path.is_file():
            continue
        parsed = _parse(path, cache)
        if parsed is None:
            return None
        lines, tree = parsed
        func = _find_function(tree, func_name)
        return LocatedFunction(path, lines, func) if func else None
    return None


def _line(lines: list[str], number: int) -> str:
    """Source text of a 1-based line number, or empty if out of range."""
    return lines[number - 1] if 0 < number <= len(lines) else ""


def scan_hooks(root: Path, rules: Iterable[Rule]) -> tuple[list[Finding], list[str]]:
    """Apply hook_function rules; returns findings plus notes about what was not checked."""
    hook_rules = [r for r in rules if isinstance(r.match, HookFunctionMatch)]
    findings: list[Finding] = []
    notes: list[str] = []
    cache: ParseCache = {}
    if not hook_rules:
        return findings, notes
    for hooks_path in find_hooks_files(root):
        parsed = _parse(hooks_path, cache)
        if parsed is None:  # per-file pass already reported the unreadable file
            continue
        hooks_lines, tree = parsed
        for hook in sorted(
            {r.match.hook for r in hook_rules if isinstance(r.match, HookFunctionMatch)}
        ):
            try:
                entries = read_hook_entries(tree, hook)
            except NotLiteralError:
                notes.append(f"{hooks_path}: {hook} is not a literal dict, not checked")
                continue
            for entry in entries:
                located = _locate(hooks_path.parent, entry.dotted, cache)
                detail = f'{hook}["{entry.key}"] -> {entry.dotted} (hooks.py:{entry.line})'
                for rule in hook_rules:
                    match = rule.match
                    if not isinstance(match, HookFunctionMatch) or match.hook != hook:
                        continue
                    if match.check == "unreadable" and located is None:
                        text = _line(hooks_lines, entry.line)
                        if rule.id not in ignored_ids(text):
                            findings.append(
                                Finding.from_rule(rule, str(hooks_path), entry.line, text, detail)
                            )
                    elif match.check == "returns_none" and located is not None:
                        line = can_return_none(located.func)
                        if line is None:
                            continue
                        text = _line(located.lines, line)
                        def_text = _line(located.lines, located.func.lineno)
                        suppressed = ignored_ids(text) | ignored_ids(def_text)
                        if rule.id not in suppressed:
                            findings.append(
                                Finding.from_rule(rule, str(located.file), line, text, detail)
                            )
    return sorted(findings, key=lambda f: (f.file, f.line, f.rule_id)), notes
