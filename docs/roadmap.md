# Roadmap

Release pattern: ship a focused v1, then release often. Each release adds one stage or one
capability; nothing ships half-built.

## v1.0 — T-30 static scanner (target: 7 days)

Already built (M0–M1.7): Python, JavaScript, Jinja print formats, hooks, SQL text, removed
fields and DocTypes, app packaging checks, `tminus env`, 236 tests, rules verified against
frappe, erpnext and hrms version-15 vs version-16 source.

| Day | Work |
|---|---|
| 1 | `--baseline` and a summary grouped by stage and severity |
| 2 | SARIF and HTML report |
| 3 | Run on a real app (`precision_mass`); fix false positives, speed, gaps |
| 4 | Missing wiki rules, each verified against framework source |
| 5 | README quickstart, docs, CHANGELOG, LICENSE, PyPI name check |
| 6 | Release workflow, wheel, tag `v1.0.0`, GitHub release |
| 7 | Buffer, demo script, `v1.0.1` fixes |

Definition of done for v1.0: `pytest`, `ruff`, `mypy --strict` green in CI; a clean install
from the built wheel runs `tminus scan` and `tminus env`; the README states plainly what is
and is not checked.

## After v1.0

| Release | Content |
|---|---|
| v1.1 | T-14 data checks (read-only database): invalid JSON, removed-DocType row counts, custom field clashes, holiday list assignments; scan code stored in the database |
| v1.2 | T-7 migrate runner and log analyzer: classify failures, clean-twice gate, table-survival comparison |
| v1.3 | T-1 rehearsal timing and T-0 cutover checklist |
| v2.0 | Thin Frappe app, T-3 differential tests (permission matrix, report numbers), `fix --apply` codemods, `rules generate` |

## Ongoing
- Keep the v16 rule set current with the Frappe wiki and releases (regenerate the frappe pins).
- `--online` checks (required apps have a version-16 branch).
- v17 rule set.
- Other frameworks: idea only.

## Open items
- PyPI name availability for `tminus` (unchecked).
- Optional: follow symlinked app folders.