"""Inline suppression comments: `# tminus: ignore[rule-id]`."""

from __future__ import annotations

import re

_IGNORE_RE = re.compile(r"#\s*tminus:\s*ignore\[([^\]]*)\]")


def ignored_ids(line: str) -> set[str]:
    """Return rule ids suppressed by an ignore comment on this line."""
    match = _IGNORE_RE.search(line)
    if not match:
        return set()
    return {part.strip() for part in match.group(1).split(",") if part.strip()}
