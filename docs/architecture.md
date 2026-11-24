# Architecture

T-MINUS is a read-only Python package (`src/tminus/`). The core never imports `frappe`.

## Layout

| Path | Role |
|---|---|
| `cli/main.py` | `scan` and `env` commands, exit codes |
| `engine/models.py`, `loader.py` | rule/finding models (pydantic), YAML loading, `target.yaml` |
| `engine/runner.py` | runs the scan passes below |
| `engine/context.py`, `names.py`, `guards.py` | per-file facts: import aliases, `try/except ImportError` regions |
| `engine/matchers/` | one function per match type (`import_path`, `call`, `doctype`, `query_syntax`, ...) |
| `engine/scanners/` | app-level passes: `hooks`, `js_ast`, `print_format`, `packaging` |
| `engine/frappe_refs.py`, `sql_refs.py`, `jinja_refs.py`, `js_refs.py` | find DocType/field references in Python, SQL text, Jinja, JavaScript |
| `engine/app_packaging.py`, `versions.py`, `env_check.py` | packaging facts, version ranges, `tminus env` |
| `engine/baseline.py`, `report/` | baselines and text, JSON, HTML, PDF and SARIF reports |
| `rules/v16/*.yaml` | the rules (data) |

## Scan passes (`tminus scan`)

1. Per Python file: parse once, build the file context, run the per-file matchers.
2. `hooks.py`: hook functions/classes, removed hooks, typed hook parameters, `doc_events`.
3. JavaScript files (tree-sitter).
4. Standard print formats (JSON + Jinja template).
5. App packaging (`pyproject.toml`, `setup.py`, `requirements.txt`, `package.json`).

Then the baseline is applied, the report is printed, and the exit code is set.

## Safety

Read-only: nothing is written except an optional baseline file you ask for. `frappe`,
`erpnext` and `hrms` themselves are skipped as upstream apps where their v15 files would only
add noise.

## Exit codes

0 clean, 1 findings at or above `--fail-on`, 2 usage error, 3 scan could not run.

## Not built yet

Data checks (T-14), the migrate runner (T-7), rehearsal and cutover (T-1/T-0), the Frappe app,
differential tests and codemods. See `roadmap.md`.
