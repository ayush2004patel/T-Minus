# T-MINUS

> Count down to a clean Frappe/ERPNext upgrade.

T-MINUS is a read-only command line scanner that finds what will break (or silently
change) when you upgrade a Frappe/ERPNext app from **v15 to v16**, before you migrate.

It reads your app's source, never your site, and never changes anything.

## Install

```bash
git clone <this repository> && cd tminus
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
```

Python 3.12 or newer is needed to run the tool (it analyses code, it does not run it).

## Use

```bash
tminus scan path/to/your_app --target v16       # scan an app (or a whole bench apps/ folder)
tminus scan path/to/your_app --target v16 --format html --output report.html --open
tminus scan path/to/your_app --target v16 --format pdf --output report.pdf --open
tminus env path/to/bench --target v16           # compare Python, Node, MariaDB, Redis with v16's needs
```

Options of `scan`:

| Option | Meaning |
|---|---|
| `--format text` / `html` / `pdf` / `json` | Terminal, browser, PDF, or machine-readable report |
| `--output FILE` | Write a report to a file and print its location instead of its contents |
| `--open` | Open a saved HTML or PDF report with the system's default application |
| `--color auto` / `always` / `never` | Use color in terminal output; `auto` is the default and disables it for saved output |
| `--fail-on error` / `warning` / `info` / `never` | Lowest severity that gives exit code 1 (default `error`) |
| `--write-baseline FILE` | Save today's findings and exit 0 |
| `--baseline FILE` | Hide findings already in the baseline; only new ones count |

Exit codes: `0` clean, `1` findings at or above `--fail-on`, `2` usage error, `3` scan could not run.

The text report starts with a plain-language checklist, then groups complete evidence by the
upgrade rule that found it. It retains the rule ID, every file/line, source snippet and
rule-provided suggested action. Terminal colors make errors, warnings and behavior reviews
easier to distinguish; saved output stays plain text by default.

The HTML report is self-contained and has collapsible location lists. The PDF report is a
shareable, paginated version of the same grouped findings. Use `--output FILE --open` to save
and open either report without shell redirection.

Silence one finding with a comment on its line: `# tminus: ignore[rule-id]` (Python, Jinja
`{# ... #}`, `pyproject.toml`) or `// tminus: ignore[rule-id]` (JavaScript).

## What it checks (stage T-30)

| Area | Examples |
|---|---|
| Python | removed stdlib modules (Python 3.14), removed or changed ERPNext/HRMS functions, `get_all` with SQL strings, `frappe.db.commit()` in `doc_events`, `get_doc(..., field=value)`, `has_permission` hooks that can return `None`, `override_doctype_class` that does not subclass |
| Fields and DocTypes | fields removed or moved (for example `acc_frozen_upto`, `gross_purchase_amount`), removed DocTypes, in Python, SQL text, query-builder variables, hook parameters |
| Client code | `frm.doc.field`, `frm.set_value(...)`, `frappe.db.get_value(...)` and similar in JavaScript; `{{ doc.field }}` in print formats |
| Hooks | hooks v16 no longer reads (`leaderboards`, `advance_payment_doctypes`, ...) |
| Packaging | `requires-python`, `frappe-dependencies` bound, dependency pins that conflict with Frappe v16, Node range |

Every rule is a YAML file in `src/tminus/rules/v16/` with the evidence it was built from. The
rules were checked against the real `frappe`, `erpnext` and `hrms` version-15 and version-16
source, and they do not fire on v16's own application code.

Findings are classified as **data**, **loud** (fails during migrate), **quiet** (fails when
the code runs) or **silent** (runs but behaves differently).

## What it does not check (yet)

A clean report means "no known problems", not "safe to upgrade".

- Your site's data (invalid JSON, custom field clashes, rows of removed DocTypes) and code
  stored in the database (Client Scripts, Server Scripts, Print Formats saved on the site)
- `bench migrate` itself (log analysis) and rehearsal timing
- Differences in behaviour between a v15 and a v16 site (permissions, report numbers)
- JavaScript in shared controller classes, child-table rows in print formats

See [docs/roadmap.md](docs/roadmap.md) for what comes next.

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy && pytest
```

To add a rule, see [docs/rule-schema.md](docs/rule-schema.md): a rule is one YAML file, and
`tests/test_rule_coverage.py` fails until it has a violating and a clean example.

## License

MIT
