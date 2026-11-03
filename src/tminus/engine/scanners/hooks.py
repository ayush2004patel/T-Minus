"""App-level scanner: read hooks.py tables and check the functions/classes they name."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from tminus.engine.frappe_refs import FieldRef, function_refs
from tminus.engine.matchers.doctype import field_hits
from tminus.engine.matchers.returns_none import can_return_none
from tminus.engine.matchers.subclass import has_external_base
from tminus.engine.models import DoctypeFieldMatch, Finding, HookClassMatch, HookFunctionMatch, Rule
from tminus.engine.names import build_alias_table
from tminus.engine.paths import is_skipped
from tminus.engine.suppress import ignored_ids

ParseCache = dict[Path, tuple[list[str], ast.Module] | None]
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


class NotLiteralError(Exception):
    """A hook table is built at run time, so it cannot be read statically."""


@dataclass(frozen=True)
class HookEntry:
    """One `DocType -> dotted path` pair from a hooks.py table."""

    key: str
    dotted: str
    line: int
    event: str = ""  # doc_events only: the event name ("validate", "on_submit", ...)


@dataclass(frozen=True)
class Located:
    """A hook target (function or class) found in the app's own source."""

    file: Path
    lines: list[str]
    tree: ast.Module
    node: ast.stmt


@dataclass(frozen=True)
class HookContext:
    """Everything known about one hook entry while rules are applied to it."""

    hooks_path: Path
    hooks_lines: list[str]
    hook: str
    entry: HookEntry
    located: Located | None


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


def _doctype_keys(key: ast.expr | None) -> list[str] | None:
    """DocType names in a doc_events key: "X", or a tuple/list of names ("X", "Y")."""
    if isinstance(key, ast.Constant) and isinstance(key.value, str):
        return [key.value]
    if isinstance(key, ast.Tuple | ast.List):
        names = [
            e.value for e in key.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
        return names if len(names) == len(key.elts) else None
    return None  # computed at run time, e.g. tuple(some_list)


def read_doc_events(tree: ast.Module) -> tuple[list[HookEntry], int]:
    """Entries of `doc_events = {"DocType": {"event": "dotted.path" | [paths]}}`.

    Also returns how many table entries could not be read (computed keys or values).
    """
    entries: list[HookEntry] = []
    skipped = 0
    for node in tree.body:
        is_target = isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "doc_events" for t in node.targets
        )
        if not (is_target and isinstance(node, ast.Assign)):
            continue
        if not isinstance(node.value, ast.Dict):
            raise NotLiteralError
        for key, value in zip(node.value.keys, node.value.values, strict=True):
            doctypes = _doctype_keys(key)
            if doctypes is None or not isinstance(value, ast.Dict):
                skipped += 1  # skip this entry only; the rest of the table is still checked
                continue
            for event, target in zip(value.keys, value.values, strict=True):
                if not (isinstance(event, ast.Constant) and isinstance(event.value, str)):
                    skipped += 1
                    continue
                try:
                    paths = _paths(target)
                except NotLiteralError:
                    skipped += 1
                    continue
                entries.extend(
                    HookEntry(name, p, target.lineno, event.value)
                    for name in doctypes
                    for p in paths
                )
    return entries, skipped


def _parse(path: Path, cache: ParseCache) -> tuple[list[str], ast.Module] | None:
    """Parse a file once and remember the result; None if it cannot be read."""
    if path not in cache:
        try:
            text = path.read_text(encoding="utf-8")
            cache[path] = (text.splitlines(), ast.parse(text, filename=str(path)))
        except (OSError, UnicodeDecodeError, SyntaxError):
            cache[path] = None
    return cache[path]


def _find_top_level(tree: ast.Module, name: str) -> ast.stmt | None:
    """Find a top-level function or class by name."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and (
            node.name == name
        ):
            return node
    return None


def _locate(pkg_dir: Path, dotted: str, cache: ParseCache) -> Located | None:
    """Resolve `app.module.name` to a function/class in this app's own source, else None."""
    parts = dotted.split(".")
    if len(parts) < 2 or parts[0] != pkg_dir.name:  # points outside this app
        return None
    module_parts, name = parts[1:-1], parts[-1]
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
        node = _find_top_level(tree, name)
        return Located(path, lines, tree, node) if node else None
    return None


def _line(lines: list[str], number: int) -> str:
    """Source text of a 1-based line number, or empty if out of range."""
    return lines[number - 1] if 0 < number <= len(lines) else ""


def _apply_rule(rule: Rule, ctx: HookContext) -> Finding | None:
    """Apply one hook rule to one hook entry; returns a finding or None."""
    match = rule.match
    if not isinstance(match, HookFunctionMatch | HookClassMatch) or match.hook != ctx.hook:
        return None
    entry = ctx.entry
    detail = f'{ctx.hook}["{entry.key}"] -> {entry.dotted} (hooks.py:{entry.line})'
    kinds = _FUNCTIONS if isinstance(match, HookFunctionMatch) else (ast.ClassDef,)
    located = ctx.located
    target = located if located is not None and isinstance(located.node, kinds) else None

    if match.check == "unreadable":  # target missing, outside the app, or the wrong kind
        if target is not None:
            return None
        text = _line(ctx.hooks_lines, entry.line)
        if rule.id in ignored_ids(text):
            return None
        return Finding.from_rule(rule, str(ctx.hooks_path), entry.line, text, detail)

    if target is None:
        return None
    node = target.node
    line: int | None = None
    if isinstance(match, HookFunctionMatch) and isinstance(
        node, ast.FunctionDef | ast.AsyncFunctionDef
    ):
        line = can_return_none(node)
    elif isinstance(node, ast.ClassDef):
        line = None if has_external_base(node, target.tree) else node.lineno
    if line is None:
        return None
    text = _line(target.lines, line)
    if rule.id in ignored_ids(text) | ignored_ids(_line(target.lines, node.lineno)):
        return None
    return Finding.from_rule(rule, str(target.file), line, text, detail)


def _param_names(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Names of the positional parameters, in order."""
    return [a.arg for a in [*func.args.posonlyargs, *func.args.args]]


def _is_instance_method(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """False for @staticmethod and @classmethod (their first parameter is not `self`)."""
    names = {d.id for d in func.decorator_list if isinstance(d, ast.Name)}
    return not names & {"staticmethod", "classmethod"}


def _target_refs(
    located: Located, doctype: str, kind: str, aliases: dict[str, str]
) -> list[FieldRef]:
    """Field references made through a hook target's document parameter (or `self`)."""
    node = located.node
    if kind == "function" and isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        params = _param_names(node)
        return function_refs(node, aliases, {params[0]: doctype}) if params else []
    if kind == "class" and isinstance(node, ast.ClassDef):
        refs: list[FieldRef] = []
        for item in node.body:  # every method sees the overridden DocType as `self`
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and _is_instance_method(
                item
            ):
                params = _param_names(item)
                if params:
                    refs += function_refs(item, aliases, {params[0]: doctype})
        return refs
    return []


def _typed_hook_findings(
    hooks_path: Path,
    tree: ast.Module,
    rules: list[Rule],
    cache: ParseCache,
    notes: list[str],
) -> list[Finding]:
    """Check field use inside functions/classes that hooks.py ties to one DocType."""
    targets: list[tuple[str, str, HookEntry]] = []  # (label, kind, entry)
    try:
        events, skipped = read_doc_events(tree)
        for e in events:
            if e.key != "*":  # "*" means every DocType: no single type to assume
                targets.append((f'doc_events["{e.key}"]["{e.event}"]', "function", e))
        if skipped:
            notes.append(f"{hooks_path}: {skipped} doc_events entries not checked (computed keys)")
    except NotLiteralError:
        notes.append(f"{hooks_path}: doc_events is not a literal dict, not checked")
    for hook, kind in (("has_permission", "function"), ("override_doctype_class", "class")):
        try:
            targets += [(f'{hook}["{e.key}"]', kind, e) for e in read_hook_entries(tree, hook)]
        except NotLiteralError:
            continue  # already reported by the hook-rule pass
    findings: dict[tuple[str, int, str, str], Finding] = {}
    alias_cache: dict[Path, dict[str, str]] = {}
    for label, kind, entry in targets:
        located = _locate(hooks_path.parent, entry.dotted, cache)
        if located is None:
            continue
        aliases = alias_cache.setdefault(located.file, build_alias_table(located.tree))
        refs = _target_refs(located, entry.key, kind, aliases)
        for rule in rules:
            if not isinstance(rule.match, DoctypeFieldMatch):
                continue
            for hit in field_hits(rule.match, refs):
                text = _line(located.lines, hit.line)
                if rule.id in ignored_ids(text):
                    continue
                detail = f"{hit.detail}  (via {label}, hooks.py:{entry.line})"
                finding = Finding.from_rule(rule, str(located.file), hit.line, text, detail)
                findings[(finding.file, finding.line, rule.id, detail)] = finding
    return list(findings.values())


def scan_hooks(root: Path, rules: Iterable[Rule]) -> tuple[list[Finding], list[str]]:
    """Apply hook rules; returns findings plus notes about what was not checked."""
    rules = list(rules)
    hook_rules = [r for r in rules if isinstance(r.match, HookFunctionMatch | HookClassMatch)]
    field_rules = [r for r in rules if isinstance(r.match, DoctypeFieldMatch)]
    findings: list[Finding] = []
    notes: list[str] = []
    if not hook_rules and not field_rules:
        return findings, notes
    cache: ParseCache = {}
    hook_names = sorted(
        {
            r.match.hook
            for r in hook_rules
            if isinstance(r.match, HookFunctionMatch | HookClassMatch)
        }
    )
    for hooks_path in find_hooks_files(root):
        parsed = _parse(hooks_path, cache)
        if parsed is None:  # per-file pass already reported the unreadable file
            continue
        hooks_lines, tree = parsed
        if field_rules:
            findings += _typed_hook_findings(hooks_path, tree, field_rules, cache, notes)
        for hook in hook_names:
            try:
                entries = read_hook_entries(tree, hook)
            except NotLiteralError:
                notes.append(f"{hooks_path}: {hook} is not a literal dict, not checked")
                continue
            for entry in entries:
                located = _locate(hooks_path.parent, entry.dotted, cache)
                ctx = HookContext(hooks_path, hooks_lines, hook, entry, located)
                for rule in hook_rules:
                    finding = _apply_rule(rule, ctx)
                    if finding is not None:
                        findings.append(finding)
    return sorted(findings, key=lambda f: (f.file, f.line, f.rule_id)), notes