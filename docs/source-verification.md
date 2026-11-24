# Source verification log

Every rule is built from evidence, not memory. This records what each group was checked against.

## Sources

| Source | Used for |
|---|---|
| Frappe wiki "Migrating to version 16" and "query-builder-migration" | the list of breaking changes |
| BWH *ERPNext Upgrade Playbook* (PDF) | failure classes, real failure cases, process |
| `frappe`, `erpnext`, `hrms` source, branches `version-15` and `version-16` (frappe 16.54.0) | verification of every rule |
| `bench` source | how `frappe-dependencies` is enforced |

## Verified per rule group

| Rules | Evidence |
|---|---|
| Removed/renamed fields, removed DocTypes | JSON diff of every DocType between version-15 and version-16, replacements checked against the v16 migration patches (fields without patch evidence say "removed") |
| Removed/changed functions | function located in v15 and absent or changed in v16 source; v16 own code gives no findings |
| `get_all` SQL strings | frappe 16.54.0 `database/query.py` (`_validate_select_field`, filter field validation); the allowed patterns are copied from it |
| `doc_events` commit | v16 `model/document.py` disables transaction control around hooks; `Database.commit()` then warns and returns; v15 has no such flag |
| `get_doc` extra keywords | v16 `get_doc` signature accepts only `for_update` and `check_permission` after `(doctype, name)` |
| Removed hooks | v15 code calls `get_hooks(...)` for them, v16 code does not; replacements are read in v16 |
| Packaging | frappe 16.54.0 `pyproject.toml` and `package.json`; CI uses Python 3.14, Node 24, MariaDB 11.8; `bench` source for the bound check |
| `has_permission`, `override_doctype_class` | Frappe wiki and playbook |

## Checked on real code

Rules were run on ERPNext, HRMS and Frappe v15 (they find real uses) and v16 (they do not
fire on application code that already works on v16; remaining v16 hits are stale test or leftover code).

## Dropped or open

- Translation helper functions (`get_lang_dict`, `get_dict`, ...): not found as plain functions in the v15 source, so no rule.
- `frappe.sendmail(now=True)`, single-value typed `== "1"`, `!= None` filters, POST-only methods, JS IIFE loading: not verified, not implemented.
- Whether data of removed DocTypes survives migrate requires a table comparison in T-7.
- `first-row-without-order-by` is a heuristic review prompt (severity `info`).
