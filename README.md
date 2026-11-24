# T-MINUS

> Count down to a clean Frappe/ERPNext upgrade.

**Latest release: v1.0.1**

[![PyPI version](https://img.shields.io/pypi/v/tminus.svg)](https://pypi.org/project/tminus/)
[![Python](https://img.shields.io/pypi/pyversions/tminus.svg)](https://pypi.org/project/tminus/)
[![License](https://img.shields.io/github/license/ayush2004patel/T-Minus.svg)](LICENSE)
[![CI](https://github.com/ayush2004patel/T-Minus/actions/workflows/ci.yml/badge.svg)](https://github.com/ayush2004patel/T-Minus/actions/workflows/ci.yml)

T-MINUS is a read-only Python CLI that identifies known compatibility risks before upgrading a
Frappe/ERPNext custom app from **v15 to v16**. It scans source code and app packaging; it never
connects to, changes, or migrates a site.

**Current release:** [PyPI](https://pypi.org/project/tminus/) ·
[GitHub repository](https://github.com/ayush2004patel/T-Minus) ·
[Issues](https://github.com/ayush2004patel/T-Minus/issues) ·
[Releases](https://github.com/ayush2004patel/T-Minus/releases) ·
[Documentation](docs/roadmap.md)

## Why T-MINUS?

Major Frappe/ERPNext upgrades can break custom apps in several ways: removed APIs can fail during
migration, a changed field can fail only when a user opens a form, and a behavior change can run
without an error at all. T-MINUS gives developers an early, evidence-based checklist so they can
fix known risks before beginning a migration rehearsal.

A clean T-MINUS report means **no known problems were found by its current rules**. It does not
guarantee that an upgrade is safe; a restored-site rehearsal is still required.

## Features

- Read-only static analysis of Python, JavaScript, print-format templates, hooks, SQL text, and
  app packaging.
- Rule-driven checks with a source reference, a violating fixture, and a clean fixture for every
  rule.
- Environment comparison for Python, Node, MariaDB, and Redis.
- Clear terminal output plus JSON, self-contained HTML, PDF, and SARIF reports.
- Baselines to focus on newly introduced findings.
- Finding suppressions for reviewed exceptions.
- CI-friendly exit codes and SARIF output for code-scanning tools.

## Installation

T-MINUS requires Python 3.12 or newer.

```bash
python3 -m pip install tminus
```

## Installation verification

```bash
tminus --version
tminus --help
```

## Quick Start

Scan a custom app for v16 compatibility risks:

```bash
tminus scan /path/to/your_app --target v16
```

Generate a shareable PDF report:

```bash
tminus scan /path/to/your_app --target v16 --format pdf --fail-on never
```

HTML, PDF, and SARIF reports are saved by default in Downloads as
`<app>-tminus-<target>-report.<format>`. HTML and PDF reports open automatically; use
`--no-open` when running in a script or CI environment.

## Typical Upgrade Workflow

1. Create a fresh v16 bench and restore a **copy** of the v15 production backup. Never test an
   upgrade on production.
2. Check the new bench environment:

   ```bash
   tminus env /path/to/v16-bench --target v16
   ```

3. Scan each custom app:

   ```bash
   tminus scan /path/to/custom_app --target v16 --format pdf --fail-on never
   ```

4. Review every finding, then fix only the custom app. Keep behavior unchanged where possible.
5. If a data fix is needed, apply and test it on a separate restored v15 test site. Take a fresh backup of that test site and use it for the next upgrade rehearsal.
**Never experiment on production data.**
6. Run a real migration rehearsal on the restored copy and read the complete migration log.

T-MINUS helps with steps 2 and 3. It does not replace the remaining steps.

## Example Reports

The default text report starts with the upgrade target, scanned application, result, and next
steps. It then groups every finding by the v16 change that caused it, preserving the rule ID,
file/line location, source snippet, technical context, and suggested action.

```text
Result: ACTION REQUIRED
Findings: 2 error, 1 warning

Errors (2)
  1. Removed Python standard library modules (1 location)
     Rule: v16-removed-python-stdlib
     Affected location: custom_app/api.py:14
```

Use PDF for a shareable developer report, HTML for a browser report, JSON for custom automation,
and SARIF for code-scanning integrations.

## Commands and Options

### `tminus scan PATH --target v16`

Scans one app folder or source file. `--target v16` is required.

| Option | Description |
|---|---|
| `PATH` | App folder or file to scan. |
| `--target v16` | Required target framework version. |
| `--format text\|json\|html\|pdf\|sarif` | Report format. Default: `text`. |
| `--output FILE` | Save a report to a specific file instead of the default Downloads location. |
| `--open / --no-open` | Open saved HTML and PDF reports or leave them closed. Default: `--open`. |
| `--color auto\|always\|never` | Control terminal colors for text reports. Default: `auto`. |
| `--fail-on error\|warning\|info\|never` | Lowest severity that exits with code 1. Default: `error`. |
| `--write-baseline FILE` | Save the current findings as a baseline and exit successfully. |
| `--baseline FILE` | Hide findings already present in a baseline or JSON report. |

Exit codes: `0` for no findings at the chosen threshold, `1` for findings at or above the
threshold, `2` for invalid usage, and `3` when the scan cannot run.

### `tminus env [PATH] --target v16`

Checks the Python, Node, MariaDB, and Redis requirements for a bench. `PATH` defaults to the
current directory and `--target v16` is required.

### Global options

| Option | Description |
|---|---|
| `--version` | Print the installed T-MINUS version. |
| `--help` | Show command help. |

## Baseline Support

Use a baseline when an app already has known upgrade findings and you want CI to report only new
ones.

Create a baseline from the current scan:

```bash
tminus scan /path/to/your_app --target v16 --write-baseline tminus-baseline.json
```

Compare later scans with that baseline:

```bash
tminus scan /path/to/your_app --target v16 --baseline tminus-baseline.json
```

Baselines identify a finding by its rule, file, snippet, and technical detail—not its line number—so
ordinary line movement does not turn an existing finding into a new one.

## SARIF and CI Integration

SARIF is a machine-readable format understood by GitHub code scanning, VS Code extensions, and
other CI tools. T-MINUS generates the file; your CI workflow is responsible for uploading it.

```bash
tminus scan /path/to/your_app --target v16 --format sarif \
  --output tminus-v16.sarif --fail-on never
```

The SARIF file retains the T-MINUS rule ID, severity, file and line location, suggested action,
technical context, and available rule references.

## Suppressing Findings

Suppress a reviewed finding on the relevant line when the code is intentionally compatible:

```python
import imp  # tminus: ignore[v16-removed-python-stdlib]
```

Use `// tminus: ignore[rule-id]` in JavaScript and `{# tminus: ignore[rule-id] #}` in Jinja or
print-format templates. Keep suppressions specific and review them during the upgrade.

## What T-MINUS Checks

All current checks are **T-30 static checks**: they inspect source and app packaging before a
site migration begins.

| Area | Examples |
|---|---|
| Python | Removed Python modules; changed or removed ERPNext/HRMS functions; SQL strings in `get_all` / `get_list`; `frappe.db.commit()` in `doc_events`; unsupported `get_doc(..., field=value)` calls. |
| Fields and DocTypes | Removed, renamed, or moved Frappe/ERPNext/HRMS fields; removed DocTypes; references in Python, SQL text, query-builder variables, hooks, JavaScript, and print formats. |
| Hooks | `has_permission` hooks that can return `None`; incorrect `override_doctype_class` inheritance; hooks v16 no longer reads. |
| Client code and templates | JavaScript field references such as `frm.doc.field`, `frm.set_value(...)`, and `frappe.db.get_value(...)`; Jinja field references in standard print-format files. |
| Packaging and environment | Python, Frappe, Node, and dependency compatibility declarations; Python, Node, MariaDB, and Redis bench requirements. |

Rules are YAML data files in [`src/tminus/rules/v16/`](src/tminus/rules/v16/). See the
[rule schema](docs/rule-schema.md) to understand how rules are defined and verified.

## Finding Classifications

T-MINUS labels findings by the kind of upgrade risk they represent:

| Classification | Meaning |
|---|---|
| **Data** | Existing site data can block a patch or become unsafe during migration. |
| **Loud code** | The issue is likely to fail visibly during import or migration. |
| **Quiet code** | The issue may fail only when a user reaches the affected feature. |
| **Silent behavior** | The code runs but its behavior can change without an error. |

## What T-MINUS Does Not Check

A clean report means “no known problems found by the current rules,” not “safe to upgrade.”

T-MINUS does not yet check:

- Site database data, including invalid JSON, custom-field clashes, and row counts for removed
  DocTypes.
- Code stored in the database, including Client Scripts, Server Scripts, and site-saved Print
  Formats.
- `bench migrate`, migration-log analysis, or rehearsal timing.
- Runtime behavior differences such as permissions and report totals.
- JavaScript in shared controller classes or child-table rows in print formats.

## Development

To contribute or run T-MINUS from source:

```bash
git clone https://github.com/ayush2004patel/T-Minus.git
cd T-Minus
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the quality checks:

```bash
ruff check .
ruff format --check .
mypy
pytest
```

To add a rule, follow the [rule schema](docs/rule-schema.md). Every rule needs a source
reference, a violating fixture, and a clean fixture; the rule-coverage tests enforce this.

For the release process, see [releasing](docs/releasing.md).

## Roadmap

The next planned stages extend T-MINUS beyond source scanning:

| Release | Focus |
|---|---|
| v1.1 | Read-only T-14 data checks: invalid JSON, removed-DocType row counts, custom-field clashes, holiday-list assignments, and site-saved code. |
| v1.2 | T-7 migration runner and log analysis. |
| v1.3 | T-1 rehearsal timing and T-0 cutover checklist. |
| v2.0 | Frappe app integration, T-3 differential tests, safe codemods, and rule generation. |

See the full [roadmap](docs/roadmap.md).

## License

T-MINUS is released under the [MIT License](LICENSE).
