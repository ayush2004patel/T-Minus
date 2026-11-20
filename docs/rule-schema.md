# Rule schema

One YAML file = one breaking change. File name = rule id. Folder = target (`src/tminus/rules/v16/`).
The loader rejects unknown keys. `tests/test_rule_coverage.py` requires every rule to have
references, a violating example and a clean example.

```yaml
id: v16-has-permission-hook-returns-none   # must equal the file name
title: has_permission hook can return None
target: v16                                # must equal the folder name
app: frappe                                # frappe | erpnext | hrms | <any app>
severity: error                            # error | warning | info
category: silent                           # data | loud | quiet | silent
stage: T-30                                # T-30 | T-14 | T-7 | T-3 | T-1 | T-0
match:                                     # see "Match types"
  type: hook_function
  hook: has_permission
  check: returns_none
message: >                                 # what breaks and why
  v15 read None as "no opinion"; v16 reads it as deny.
replacement: >                             # what to do instead
  Return True explicitly at the end of the function.
fix: before                                # before | with-upgrade
autofix: none                              # none | safe | review (autofix is not implemented yet)
confidence: high                           # high | medium | low (default high)
references:                                # required: the evidence the rule was built from
  - "https://github.com/frappe/frappe/wiki/Migrating-to-version-16"
```

## Match types

| `type` | Extra keys | Finds |
|---|---|---|
| `import_path` | `modules` | imports of removed modules (skips `try/except ImportError`) |
| `call` | `paths`, `check`, `count`, `names` | removed or changed functions; `check`: `removed`, `keyword_only`, `positional_count` (needs `count`), `first_arg_named` (needs `names`), `keywords_not_in` (needs `names`, `count`) |
| `hook_function` | `hook`, `check` | functions named in a `hooks.py` table; `check`: `returns_none`, `unreadable`, `commits` (`frappe.db.commit()` in a `doc_events` function) |
| `hook_class` | `hook`, `check` | classes named in a hooks table; `check`: `no_base`, `unreadable` |
| `hook_defined` | `hooks` (name: note) | hooks in `hooks.py` that v16 no longer reads |
| `doctype_field` | `doctypes` (doctype: {field: note}) | removed/renamed fields in Python, SQL text, query-builder variables, hook parameters, JavaScript, print formats |
| `doctype_name` | `names` (doctype: note) | removed DocTypes passed to a Frappe API |
| `package` | `check`, `versions`, `pins` | packaging files; `check`: `requires_python`, `frappe_bound`, `frappe_bound_missing`, `node_engine` (need `versions`), `dependency_pins` (needs `pins`) |
| `query_syntax` | `check` | `get_all`/`get_list` calls; `check`: `sql_strings`, `first_row_unordered` |

## target.yaml

`rules/<target>/target.yaml` holds `target`, `checked_on`, `note` and `requirements`
(`python`, `node`, `mariadb`, `redis`, each with `minimum`, optional `below` and
`recommended`, and a `source`). `tminus env` reads the requirements.

## Suppression and baselines

`# tminus: ignore[rule-id]` on the line (`//` in JavaScript). `--write-baseline` / `--baseline`
hide findings that already exist; a finding is identified by rule, file, snippet and detail,
not by line number.