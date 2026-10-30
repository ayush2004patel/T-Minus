# DECISIONS

Short decision records. Add new ones at the bottom. Status: accepted | superseded.

| # | Date | Decision | Why | Status |
|---|---|---|---|---|
| 1 | 2026-10-30 | Project name: T-MINUS, CLI `tminus` | Countdown maps to upgrade stages T-30..T-0 | accepted |
| 2 | 2026-10-30 | Architecture: standalone Python CLI core + thin Frappe app | CI use without a bench, plus UI and runtime checks | accepted |
| 3 | 2026-10-30 | Read-only by default; mutation only via `tminus fix --apply` | Safety; matches playbook rules | accepted (confirmed by user's approval of stage design; re-confirm if disputed) |
| 4 | 2026-10-30 | v1 scope: Frappe/ERPNext v15 -> v16 only | Engine stays version-agnostic; other frameworks are a later idea | accepted (same note as #3) |
| 5 | 2026-10-30 | Stack: Python 3.12+, typer, ast + libcst, tree-sitter, jinja2 parser, YAML + pydantic v2, PyMySQL/mariadb read-only, pytest, ruff, mypy | See docs/tech-stack.md | accepted |
| 6 | 2026-10-30 | Core never imports `frappe`; live-Frappe checks live in `tminus_app` | Core must run anywhere | accepted |
| 7 | 2026-10-30 | Project history kept in repo files (DEVLOG, DECISIONS, git log) | Continuity across work sessions | accepted |
