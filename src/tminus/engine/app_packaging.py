"""Read an app's packaging files: Python range, frappe bound, dependencies, Node engine."""

from __future__ import annotations

import ast
import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement


@dataclass(frozen=True)
class Where:
    """A value read from a packaging file, with the file and line it came from."""

    value: str
    file: Path
    line: int


@dataclass(frozen=True)
class Dependency:
    """A dependency of the app: normalized name, version specifier text, and where it is."""

    name: str
    spec: str
    where: Where


@dataclass
class AppPackaging:
    """Everything the compatibility rules need to know about one app."""

    name: str
    root: Path
    anchor: (
        Path  # file to point at when something is missing (pyproject.toml, setup.py or the root)
    )
    requires_python: Where | None = None
    frappe_bound: Where | None = None
    node_engine: Where | None = None
    dependencies: list[Dependency] = field(default_factory=list)


def normalize(name: str) -> str:
    """PEP 503 name normalization: lower case, runs of `-_.` become `-`."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _line_of(text: str, pattern: str) -> int:
    """Line number (1-based) of the first match of a regex, or 1."""
    match = re.search(pattern, text, re.MULTILINE)
    return 1 + text.count("\n", 0, match.start()) if match else 1


def _dependency(requirement: str, file: Path, line: int) -> Dependency | None:
    """Parse one requirement string; None for URLs, options and anything unreadable."""
    try:
        parsed = Requirement(requirement.strip())
    except InvalidRequirement:
        return None
    if parsed.url:  # direct references have no version range to compare
        return None
    return Dependency(normalize(parsed.name), str(parsed.specifier), Where(requirement, file, line))


def _from_pyproject(path: Path, app: AppPackaging) -> None:
    """Fill the app facts from pyproject.toml."""
    text = path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return
    project = data.get("project", {})
    app.name = project.get("name", app.name)
    if isinstance(project.get("requires-python"), str):
        line = _line_of(text, r"^requires-python\s*=")
        app.requires_python = Where(project["requires-python"], path, line)
    bound = data.get("tool", {}).get("bench", {}).get("frappe-dependencies", {}).get("frappe")
    if isinstance(bound, str):
        app.frappe_bound = Where(bound, path, _line_of(text, r"^frappe\s*="))
    for requirement in project.get("dependencies", []):
        if isinstance(requirement, str):
            line = _line_of(text, re.escape(f'"{requirement}"'))
            if dep := _dependency(requirement, path, line):
                app.dependencies.append(dep)


def _setup_keyword(tree: ast.Module, keyword: str) -> ast.expr | None:
    """The value of a keyword argument of the setup(...) call."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = (
                node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            )
            if name == "setup":
                for kw in node.keywords:
                    if kw.arg == keyword:
                        return kw.value
    return None


def _from_setup_py(path: Path, app: AppPackaging) -> None:
    """Fill the app facts from a legacy setup.py (literal values only)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return
    required = _setup_keyword(tree, "python_requires")
    if isinstance(required, ast.Constant) and isinstance(required.value, str):
        app.requires_python = Where(required.value, path, required.lineno)
    install = _setup_keyword(tree, "install_requires")
    if isinstance(install, ast.List | ast.Tuple):
        for item in install.elts:
            is_str = isinstance(item, ast.Constant) and isinstance(item.value, str)
            text = item.value if isinstance(item, ast.Constant) and is_str else None
            if isinstance(text, str) and (dep := _dependency(text, path, item.lineno)):
                app.dependencies.append(dep)


def _from_requirements(path: Path, app: AppPackaging) -> None:
    """Fill dependencies from requirements.txt (one requirement per line)."""
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-") and (dep := _dependency(line, path, number)):
            app.dependencies.append(dep)


def _from_package_json(path: Path, app: AppPackaging) -> None:
    """Fill the Node engine range from package.json."""
    text = path.read_text(encoding="utf-8")
    try:
        engines = json.loads(text).get("engines", {})
    except ValueError:
        return
    node = engines.get("node") if isinstance(engines, dict) else None
    if isinstance(node, str):
        app.node_engine = Where(node, path, _line_of(text, r'"node"\s*:'))


def read_app(root: Path) -> AppPackaging | None:
    """Read the packaging files in an app's repository root; None if there are none."""
    pyproject, setup_py = root / "pyproject.toml", root / "setup.py"
    requirements, package_json = root / "requirements.txt", root / "package.json"
    if not any(p.is_file() for p in (pyproject, setup_py, requirements)):
        return None
    anchor = pyproject if pyproject.is_file() else setup_py if setup_py.is_file() else root
    app = AppPackaging(name=root.name, root=root, anchor=anchor)
    if pyproject.is_file():
        _from_pyproject(pyproject, app)
    if setup_py.is_file():
        _from_setup_py(setup_py, app)
    if requirements.is_file() and not app.dependencies:  # setup.py usually reads this file
        _from_requirements(requirements, app)
    if package_json.is_file():
        _from_package_json(package_json, app)
    return app
