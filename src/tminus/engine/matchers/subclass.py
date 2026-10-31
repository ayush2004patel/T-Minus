"""Decide whether a class inherits from something defined outside its own module."""

from __future__ import annotations

import ast


def _walk(cls: ast.ClassDef, local: dict[str, ast.ClassDef], seen: frozenset[str]) -> bool:
    """True if some base of this class (directly or through local classes) is external."""
    if cls.name in seen:  # guard against circular local bases
        return False
    seen = seen | {cls.name}
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id == "object":  # `object` adds nothing
            continue
        if isinstance(base, ast.Name) and base.id in local:  # follow classes defined here
            if _walk(local[base.id], local, seen):
                return True
            continue
        return True  # imported name, dotted path, Generic[T], ...: assume external
    return False


def has_external_base(cls: ast.ClassDef, tree: ast.Module) -> bool:
    """True if the class inherits from at least one class not defined in this file."""
    local = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    return _walk(cls, local, frozenset())
