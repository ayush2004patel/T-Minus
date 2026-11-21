"""Parse Python source without printing warnings about the code being scanned."""

from __future__ import annotations

import ast
import warnings


def parse(source: str, filename: str = "<unknown>") -> ast.Module:
    """ast.parse that stays quiet about the scanned code (for example an invalid `\\s` escape)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ast.parse(source, filename=filename)
