# Architecture

## Shape: CLI core + thin Frappe app

```
tminus/                      (PyPI: tminus — no frappe import)
  cli/                       typer commands: scan data trial diff rehearse cutover report fix rules
  engine/
    loader.py                load + validate YAML rules (pydantic)
    matchers/                one module per match type
    scanners/
      python_ast.py          stdlib ast; libcst for fixes
      js_ts.py               tree-sitter (js, ts, vue)
      scss.py
      jinja.py               jinja2 Environment.parse
      hooks.py               hooks.py reader
      bench.py               python/node/apps.txt/pyproject checks
      site_code.py           Server/Client Scripts, Reports, Print Formats, ...
    data/                    read-only SQL checks (PyMySQL/mariadb)
    runner/                  bench wrapper: restore, migrate, tee log
    logparse/                log classifier -> data|loud|quiet|silent
    diff/                    compares two JSON snapshots (v15 vs v16)
    report/                  rich, json, sarif, html, md
    codemods/                libcst fixers (opt-in)
  rules/<target>/            YAML rules + target.yaml
tminus_app/                  (Frappe app — thin)
  doctype/ tminus_scan, tminus_finding
  api.py                     enqueue core as a library
  snapshot.py                runtime probes executed inside a live site
  page/ tminus_dashboard
```

## Data flow
1. **Inputs:** code path or bench, optional site (read-only DB user), target version, optional baseline.
2. **Engine** loads rules for the target, runs scanners, produces `Finding` objects.
3. **Finding:** `rule_id, severity, category, stage, file, line, snippet, message, replacement, fix_timing, autofix, references`.
4. **Report** groups by stage, category and severity; lists "not checked" explicitly.
5. **Snapshots:** `tminus_app.snapshot` runs inside v15 and v16 benches and writes JSON (permission matrix, report outputs, list order); core `diff` compares them. This is why the diff layer needs the Frappe app and the core does not import frappe.

## Safety model
- Core opens the DB with a read-only user; it refuses to run write statements.
- `trial`/`rehearse` refuse to run unless the target site is flagged as a restored copy (`--i-know-this-is-a-copy` or site_config marker); unknown site => stop.
- `fix --apply` only edits files in custom apps, one commit per fix, never `apps/frappe|erpnext|hrms`.
- Data fixes are never applied: T-MINUS writes the script and stops for review.

## Exit codes
0 clean at/above `--fail-on`; 1 findings; 2 usage error (unknown target/app, wrong site, bench already on target); 3 scan could not run.

## Key design decisions
| Decision | Reason |
|---|---|
| Core never imports frappe | Runs in CI and on any machine |
| Runtime checks live in the Frappe app | Need real permission/report APIs |
| Rules are YAML | Adding a rule needs no engine change |
| tree-sitter for JS | Removes line-by-line regex false positives |
| libcst only for fixes | `ast` is enough for detection and faster |
