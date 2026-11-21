# Tech stack

## In use

| Concern | Choice |
|---|---|
| Language | Python 3.12+ (the tool analyses code, it does not run it) |
| Packaging | `pyproject.toml`, hatchling |
| CLI | typer |
| Python analysis | stdlib `ast` |
| JavaScript | tree-sitter (`tree-sitter`, `tree-sitter-javascript`) |
| Jinja (print formats) | expressions read as Python with `ast` (no Jinja library) |
| Rules and models | YAML + pydantic v2 |
| Version ranges | `packaging` |
| Tests | pytest, fixtures, rule-coverage test |
| Quality | ruff (lint and format), mypy `--strict` |
| CI | GitHub Actions |
| Reports | terminal text, JSON, self-contained HTML, PDF and SARIF 2.1.0 |

## Planned (not built yet)

libcst codemods, a read-only database connector (T-14), a bench runner for migrate
(T-7), a thin Frappe app with differential tests, an MCP server.
