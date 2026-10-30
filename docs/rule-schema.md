# Rule schema

One YAML file = one breaking change. File name = rule id. Folder = target (`rules/v16/`).
Loader rejects unknown keys. Inspired by Preflight's format, extended with `category`, `stage`, `autofix`, `confidence`.

```yaml
id: v16-has-permission-hook-returns-none
title: has_permission hook can return None
target: v16
app: frappe                     # frappe | erpnext | hrms | payments | <any app>
severity: error                 # error | warning | info
category: silent                # data | loud | quiet | silent
stage: T-30                     # first stage that can detect it
match:
  type: returns_none
  keys: [has_permission]
message: >
  v15 read None as "no opinion" and allowed access; v16 reads it as deny.
replacement: >
  Return True explicitly at the end of the function.
fix: before                     # before | with-upgrade
autofix: none                   # none | safe | review
confidence: high                # high | medium | low
shim: |
  # optional snippet that runs on both versions
references:
  - https://github.com/frappe/frappe/pull/24253
```

`target.yaml` per folder: `released`, `checked` (date), `against` (e.g. `frappe v16.x`). Report header prints them.

## Match types
| Type | Finds |
|---|---|
| `import_path` | import/use of a module or dotted path (skips `try/except ImportError` and version-gated code) |
| `call` | Python call, optional kwargs / positional count / private URL host / return arity |
| `hook_key` | hook declared in `hooks.py` |
| `override_subclass` | `override_doctype_class` not subclassing the controller |
| `returns_none` / `unreadable_function` | hooked function that can return None / cannot be read |
| `missing_hook` | app ships files but lacks a hook |
| `doctype` | removed doctype named anywhere (calls, dicts, SQL, hooks, links, custom fields) |
| `doctype_field` | removed/renamed field, including doc-typed attribute access |
| `select_field` | query field forms the target rejects (SQL function strings) |
| `undeclared_import` | package frappe no longer installs and app does not declare |
| `js_query` (new) | tree-sitter query over JS/TS/Vue |
| `jinja_expr` (new) | variable/filter/call use in Jinja templates |
| `expr_field` (new) | field used in `depends_on`, `fetch_from`, conditions |
| `site_record` | records on the site chosen by filters |
| `sql_check` (new) | read-only SQL returning offending rows or counts (data stage) |
| `field_clash` (new) | custom field name equals a new standard field |
| `log_pattern` (new) | regex over migrate log, with category |
| `snapshot_diff` (new) | metric that must match between v15 and v16 snapshots |
| `bench_python`, `requires_python`, `frappe_bound`, `dependency_pins`, `required_apps` | bench/app compatibility |
| `bench_node`, `target_branch`, `dependency_wheels` | `--online` only |

## Suppression
`# tminus: ignore[rule-id]` on the line, `--baseline report.json` for existing findings.

## Testing a rule
Violation line in `tests/fixtures/violations.*`, clean line in `clean.*`, entry in the scanner test; `test_rule_coverage.py` fails for any rule without a violation fixture.

## Rule generator
`tminus rules generate --app erpnext --from version-15 --to version-16` diffs DocType JSON (removed/renamed fields and doctypes) and Python public symbols (removed/renamed functions, signature changes) and writes candidate rules to `rules/<target>/_candidates/` for human review. Candidates are never loaded until promoted.
