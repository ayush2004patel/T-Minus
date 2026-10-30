"""Matchers: one function per rule match type."""

from __future__ import annotations

import ast
from collections.abc import Callable

from tminus.engine.matchers.import_path import match_import_path
from tminus.engine.models import Rule

Matcher = Callable[[ast.AST, Rule], list[int]]  # returns matching line numbers

MATCHERS: dict[str, Matcher] = {
    "import_path": match_import_path,
}
