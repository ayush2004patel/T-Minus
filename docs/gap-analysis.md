# Gap analysis

Sources: kaulith/preflight docs (README, overview, rules, writing-a-rule), BWH *ERPNext Upgrade Playbook*, Frappe wiki *Migrating to version 16*.
Source code of Preflight was not reviewed; items marked "no rule found" are based on its published rule list.

## What Preflight does well (keep)
- Rules as validated YAML, proof link per rule, `fix: before | with-upgrade`, optional `shim`.
- Fixtures for violations and clean cases, with a rule-coverage test.
- Skips code written to survive the change (`try/except ImportError`, version-gated code).
- Bench compatibility checks (Python, node, `required_apps`, dependency pins, wheels).
- `--baseline`, `preflight: ignore[rule]`, SARIF/HTML output, exit codes 0-3.
- Honest "not checked" reporting.

## More Preflight features to keep
- Upstream apps (on frappe's own version branch) listed apart and not counted; `--app` counts them.
- Findings in patches already run (Patch Log) listed apart; patches still to run are counted and marked.
- Disabled Server/Client Scripts skipped; `--skip-tests`; `--open`; built files skipped; `--path` mode reports what it could not check.
- Reads site records for: workspaces without a module, private workspaces, Repost Allowed Types.

## Gaps T-MINUS closes
| # | Gap | Source | T-MINUS answer |
|---|---|---|---|
| 1 | Only frappe + ERPNext rules (113) | Preflight rules.md | Rule generator for any app (hrms, payments, india_compliance, custom) |
| 2 | Rules written by hand per version | writing-a-rule.md | Branch-diff rule generator, human reviewed |
| 3 | Static only; cannot see silent behaviour | overview.md "Limits" | Differential tests (T-3) |
| 4 | Reads only some site records (workspaces, repost types, customisations); no integrity checks such as bad `item_tax_rate` JSON that crashes an ERPNext patch | overview.md, Playbook | `tminus data` (T-14) |
| 5 | No row counts for doctypes leaving the framework. Sources disagree on whether their data is dropped (Playbook) or survives (Preflight) | Playbook, rules.md | Row counts at T-14, plus a table-survival comparison before/after migrate at T-7 to settle it per site |
| 6 | Does not run or read `bench migrate` | Playbook | `tminus trial` log analysis; flags "Skipping fixture ... ImportError" warnings with exit 0 |
| 7 | Custom field vs new standard field clash not detected | Playbook | Compare custom fields to target's standard fields |
| 8 | Site-saved code list omits Print Formats (Jinja), Email Templates, `depends_on`/`fetch_from` expressions | overview.md | Jinja + expression scanning |
| 9 | JS matched line by line with regex | overview.md | tree-sitter parsing |
| 10 | No autofix | overview.md | Opt-in libcst codemods for safe rules |
| 11 | Sort change `modified`→`creation` deliberately not covered | rules.md "Not covered" | Targeted heuristics: first/last-row logic without `order_by`, DocType `sort_field`, differential list check |
| 12 | Upgrade steps not covered | overview.md | Stages T-7 to T-0 |
| 13 | HRMS changes (Holiday List Assignment, removed benefit helpers) not covered | Playbook | HRMS rule set + data check for Employee holiday lists |
| 14 | Wiki items with no rule found | Wiki | See `v16-change-catalog.md` (marked NEW) |

## Wiki items with no Preflight rule found (candidates)
`db.commit()` in doc hooks; `db.get_value` casting single doctypes; JS in Reports/Charts/Pages evaluated as IIFEs;
`get_doc(dt, name, field=value)` no longer updates; `sendmail(now=True)` no longer commits; POST-only methods
(`logout`, `web_logout`, `upload_file`, `send_login_link`); `site_cache` with unhashable args; `!= None` filter fix;
time-field default removed; `meta.get_valid_columns` excludes virtual fields; `get_translated_dict` hook and translate helpers removed;
System Console admin-only; Country `code` now required.
