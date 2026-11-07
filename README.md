# T-MINUS

> Count down to a clean upgrade.

T-MINUS prepares a Frappe/ERPNext site for a major-version upgrade (v1 target: **v15 → v16**).
It scans code, site data and customisations, rehearses the migration on a restored copy,
compares v15 against v16 behaviour, and produces a readiness report for every stage of the countdown.

**Read-only by default.** Nothing is modified on a site, a bench or in your code unless you
explicitly run `tminus fix --apply`.

## Countdown

| Stage | Command | What it does |
|---|---|---|
| T-30 | `tminus scan` | Static scan: custom apps, patches, site-saved code (Server/Client Scripts, Reports, Print Formats, ...), customisations, bench and app compatibility |
| T-14 | `tminus data` | Read-only data checks: invalid JSON columns, row counts for doctypes that leave the framework, custom-field clashes, records v16 reads differently |
| T-7  | `tminus trial` | Trial migrate on a restored copy, full log analysis, failures classified |
| T-3  | `tminus diff` | Differential tests v15 vs v16: permission matrix, report numbers, list order, smoke tests |
| T-1  | `tminus rehearse` | Timed dry run on a fresh backup, rollback plan check |
| T-0  | `tminus cutover` | Cutover checklist and go/no-go summary |

Plus: `tminus report` (html / json / sarif / md), `tminus fix` (opt-in codemods),
`tminus rules generate` (candidate rules from a branch diff).

## Packages

- `tminus` — core Python package and CLI. Runs anywhere, including CI with no bench (`--path`).
- `tminus_app` — thin Frappe app. Desk UI, stored scan history, and the runtime checks that need a live Frappe (permission matrix, report execution).

## Status

v1.0 in progress: the T-30 static scanner is complete (M0–M1.7). See docs/roadmap.md.

## Development

```bash
python3 -m venv .venv && . .venv/bin/activate   # create and enter a virtual env
pip install -e ".[dev]"                          # install tminus + dev tools
pytest                                           # run tests
ruff check . && ruff format --check .            # lint and formatting
mypy                                             # type check
tminus scan tests/fixtures/violations.py --target v16   # try the scanner
```

Layout: `src/tminus/` (code), `src/tminus/rules/<target>/` (YAML rules), `tests/` (tests + fixtures), `docs/` (design).

