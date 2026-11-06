"""Version-range helpers for PEP 440 (Python packages) and npm-style (Node) ranges."""

from __future__ import annotations

import re

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version


def spec_allows(spec: str, version: str) -> bool | None:
    """True/False if a PEP 440 specifier allows the version; None if it cannot be read."""
    try:
        return SpecifierSet(spec).contains(version, prereleases=True)
    except InvalidSpecifier:
        return None


def _candidates(*specs: SpecifierSet) -> set[Version]:
    """Versions worth testing: every version named in the specs, plus a few neighbours."""
    found: set[Version] = set()
    for spec in specs:
        for item in spec:
            try:
                found.add(Version(item.version.removesuffix(".*")))
            except InvalidVersion:
                continue
    out: set[Version] = set()
    for v in found:
        major, minor, micro = (*v.release, 0, 0)[:3]
        for release in (
            (major, minor, micro),
            (major, minor, micro + 1),  # just above an exclusive lower bound
            (major, minor + 1, 0),
            (major + 1, 0, 0),
            (major, max(minor - 1, 0), 0),
        ):
            out.add(Version(".".join(map(str, release))))
    return out


def specs_conflict(spec_a: str, spec_b: str) -> bool | None:
    """True if no version can satisfy both specifiers; None if either cannot be read."""
    try:
        a, b = SpecifierSet(spec_a), SpecifierSet(spec_b)
    except InvalidSpecifier:
        return None
    return not any(a.contains(v, prereleases=True) and b.contains(v, prereleases=True)
                   for v in _candidates(a, b))  # fmt: skip


_PARTIAL = re.compile(r"^[vV=]?(\d+|[xX*])(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?$")


def _partial(text: str) -> tuple[int, ...] | None:
    """`20`, `20.1`, `20.1.3`, `20.x` as a tuple of the numbers given (wildcards cut it short)."""
    match = _PARTIAL.match(text)
    if not match:
        return None
    parts: list[int] = []
    for group in match.groups():
        if group is None or group in "xX*":
            break
        parts.append(int(group))
    return tuple(parts)


def _bump(parts: tuple[int, ...]) -> tuple[int, int, int]:
    """The first version above everything that starts with `parts` (20 -> 21.0.0)."""
    if not parts:
        return (10**9, 0, 0)
    padded = [*parts, 0, 0][:3]
    index = len(parts) - 1
    padded[index] += 1
    for later in range(index + 1, 3):
        padded[later] = 0
    return (padded[0], padded[1], padded[2])


def _pad(parts: tuple[int, ...]) -> tuple[int, int, int]:
    """Pad a partial version with zeros: 20 -> 20.0.0."""
    return ((*parts, 0, 0, 0)[0], (*parts, 0, 0, 0)[1], (*parts, 0, 0, 0)[2])


def _comparator_allows(token: str, version: tuple[int, int, int]) -> bool | None:
    """One npm comparator (`>=18`, `^20`, `~20.1`, `20.x`, ...) against a version."""
    operator = re.match(r"^(>=|<=|>|<|\^|~|=)?\s*(.*)$", token)
    if operator is None:
        return None
    op, rest = operator.group(1) or "=", operator.group(2)
    parts = _partial(rest)
    if parts is None:
        return None
    low, high = _pad(parts), _bump(parts)
    if op == ">=":
        return version >= low
    if op == ">":
        return version >= high
    if op == "<=":
        return version < high
    if op == "<":
        return version < low
    if op == "^":
        return low <= version < _bump(parts[:1])
    if op == "~":
        return low <= version < _bump(parts[:2] if len(parts) >= 2 else parts[:1])
    return low <= version < high  # "=" or a bare version


def node_allows(range_text: str, version: str) -> bool | None:
    """True/False if an npm-style range allows the version; None if it cannot be read."""
    target = _partial(version)
    if target is None or not target:
        return None
    wanted = _pad(target)
    for alternative in range_text.split("||"):
        tokens = alternative.replace(">= ", ">=").replace("<= ", "<=").split()
        if "-" in tokens:  # hyphen ranges are not supported
            return None
        if not tokens:  # an empty alternative means "any version"
            return True
        results = [_comparator_allows(t, wanted) for t in tokens]
        if any(r is None for r in results):
            return None
        if all(results):
            return True
    return False
