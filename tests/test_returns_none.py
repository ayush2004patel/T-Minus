"""Tests for the can-this-function-return-None analysis."""

import ast

from tminus.engine.matchers.returns_none import FunctionNode, can_return_none


def _func(source: str) -> FunctionNode:
    """Parse source and return its first function."""
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    return node


def test_falls_off_the_end_reports_def_line() -> None:
    """A function with a return only in one branch can return None at the end."""
    assert can_return_none(_func("def f():\n    if x:\n        return True\n")) == 1


def test_explicit_return_none_reports_that_line() -> None:
    """`return None` is reported at its own line."""
    assert (
        can_return_none(_func("def f():\n    if x:\n        return False\n    return None\n")) == 4
    )


def test_bare_return() -> None:
    """A bare `return` returns None."""
    assert can_return_none(_func("def f():\n    return\n")) == 2


def test_all_paths_return() -> None:
    """A final `return True` makes the function safe."""
    assert (
        can_return_none(_func("def f():\n    if x:\n        return False\n    return True\n"))
        is None
    )


def test_if_else_both_return() -> None:
    """Both branches returning means nothing falls through."""
    assert (
        can_return_none(
            _func("def f():\n    if x:\n        return 1\n    else:\n        return 2\n")
        )
        is None
    )


def test_if_without_else_falls_through() -> None:
    """An `if` with a return but no else can fall through."""
    assert can_return_none(_func("def f():\n    if x:\n        return 1\n")) == 1


def test_try_except_both_return() -> None:
    """try/except where every path returns is safe."""
    src = "def f():\n    try:\n        return True\n    except Exception:\n        return False\n"
    assert can_return_none(_func(src)) is None


def test_raise_at_end_is_safe() -> None:
    """Ending in raise never returns None."""
    assert can_return_none(_func("def f():\n    raise ValueError()\n")) is None


def test_while_true_with_return_is_safe() -> None:
    """`while True` with no break cannot fall through."""
    assert can_return_none(_func("def f():\n    while True:\n        return True\n")) is None


def test_while_true_with_break_falls_through() -> None:
    """A break lets the loop end, so the function can fall off the end."""
    assert can_return_none(_func("def f():\n    while True:\n        break\n")) == 1


def test_nested_function_return_none_is_ignored() -> None:
    """A nested function's `return None` is not this function's return."""
    src = "def f():\n    def g():\n        return None\n    return True\n"
    assert can_return_none(_func(src)) is None


def test_with_block_returning_is_safe() -> None:
    """A return inside `with` counts."""
    assert can_return_none(_func("def f():\n    with a:\n        return True\n")) is None


def test_docstring_only_function() -> None:
    """A function that does nothing returns None."""
    assert can_return_none(_func('def f():\n    """doc"""\n')) == 1


def test_match_with_wildcard_all_return() -> None:
    """A match with a wildcard case where all cases return is safe."""
    src = (
        "def f(x):\n    match x:\n        case 1:\n            return True\n"
        "        case _:\n            return False\n"
    )
    assert can_return_none(_func(src)) is None
