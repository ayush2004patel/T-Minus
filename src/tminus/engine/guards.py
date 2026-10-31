"""Find code protected by try/except ImportError (written to survive the change)."""

from __future__ import annotations

import ast

_IMPORT_ERRORS = {"ImportError", "ModuleNotFoundError"}  # handlers that make an import safe


def catches_import_error(handler: ast.ExceptHandler) -> bool:
    """True if this except clause names ImportError or ModuleNotFoundError."""
    exc = handler.type
    if isinstance(exc, ast.Name):
        return exc.id in _IMPORT_ERRORS
    if isinstance(exc, ast.Tuple):  # except (ImportError, OSError):
        return any(isinstance(e, ast.Name) and e.id in _IMPORT_ERRORS for e in exc.elts)
    return False


def guarded_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """Line ranges of try bodies whose except clause catches ImportError."""
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(catches_import_error(h) for h in node.handlers):
            last = node.body[-1]
            ranges.append((node.body[0].lineno, last.end_lineno or last.lineno))
    return ranges


def is_guarded(line: int, ranges: list[tuple[int, int]]) -> bool:
    """True if the line sits inside one of the guarded ranges."""
    return any(start <= line <= end for start, end in ranges)
