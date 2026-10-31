"""Tests for the has-an-external-base-class analysis."""

import ast

from tminus.engine.matchers.subclass import has_external_base


def _check(source: str, name: str) -> bool:
    """Parse source and run the analysis on the class called `name`."""
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    return has_external_base(cls, tree)


def test_no_base() -> None:
    """A class with no bases does not inherit from anything external."""
    assert _check("class A:\n    pass\n", "A") is False


def test_only_object() -> None:
    """`object` does not count as a real base."""
    assert _check("class A(object):\n    pass\n", "A") is False


def test_imported_base() -> None:
    """An imported base counts as external."""
    assert _check("from x import Base\nclass A(Base):\n    pass\n", "A") is True


def test_dotted_base() -> None:
    """A dotted base such as frappe.model.document.Document counts as external."""
    assert _check("class A(frappe.model.document.Document):\n    pass\n", "A") is True


def test_local_base_without_base() -> None:
    """Inheriting only from a local class with no base is not external."""
    assert _check("class H:\n    pass\nclass A(H):\n    pass\n", "A") is False


def test_local_chain_ending_in_import() -> None:
    """A local chain that ends in an imported class is external."""
    src = "from x import Base\nclass M(Base):\n    pass\nclass A(M):\n    pass\n"
    assert _check(src, "A") is True


def test_mixin_plus_imported_base() -> None:
    """One external base among several is enough."""
    assert _check("from x import B\nclass M:\n    pass\nclass A(M, B):\n    pass\n", "A") is True


def test_generic_subscript_base() -> None:
    """A subscripted base such as Generic[T] counts as external."""
    assert _check("class A(Generic[T]):\n    pass\n", "A") is True


def test_circular_local_bases_do_not_crash() -> None:
    """Circular local bases terminate and report no external base."""
    assert _check("class A(B):\n    pass\nclass B(A):\n    pass\n", "A") is False
