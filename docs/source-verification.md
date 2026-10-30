# Source verification log

Which source says what, and where they disagree. Fetched 2026-10-30.

| Source | Version / date | Verified |
|---|---|---|
| Frappe wiki "Migrating to version 16" | last edited 2026-08-17, 31 revisions | read in full |
| Preflight `docs/rules.md` | rules checked 2026-10-25 vs frappe v16.53.0 (113 rules: 77 frappe+bench, 36 ERPNext) | read in full |
| Preflight `docs/overview.md` | same | read in full |
| Preflight `docs/writing-a-rule.md` | - | read earlier; not re-read |
| Preflight `getting-started`, `reading-a-report`, `upgrade-checklist`, source code | - | not read |
| BWH ERPNext Upgrade Playbook (PDF) | v15 -> v16 | read in full (user upload) |

## Confirmed
- Python 3.14+ and Node 24+ (wiki, PF `v16-bench-python`, `v16-bench-node`).
- PF has no rule for: `db.commit()` in hooks, `db.get_value` single-doctype casting, JS IIFE loading, POST-only methods, `sendmail(now=True)`, `get_doc(field=value)`, `site_cache` args, `!= None`, time-field default, `get_valid_columns`, System Console, Country code, `bench version`, removal of translation helpers (only the country_info deprecation), Print Formats / Email Templates / expression fields in its site-code scan.
- PF scans JS/SCSS line by line (stated in its Limits).
- PF reads some site records (workspaces, Repost Allowed Types) and customisations.

## Disagreement (open)
- **Data of extracted-app doctypes.** Playbook: migrate deletes orphan doctypes under "Removing orphan doctypes..." and the data goes with them. Preflight: tables survive the upgrade, ORM reads raise. T-MINUS must test this per site (table list before/after migrate) instead of assuming either.

## Corrections made to earlier drafts
- Octicons: PF only, not in wiki.
- "Preflight does no data checks" was too strong: it reads some site records.
- Catalog was missing ~40 items present in PF's rule list; added under "Additional items".
- Wiki heading names the hook `override_doctype`; PF and code use `override_doctype_class`.

## Still to verify
- Every catalog row against framework source or merged PR before it becomes a rule.
- Exact "removed fields" list on Company, Customer, Item, Payment Entry, Job Card, Journal Entry (needs PF rule data or ERPNext diff).
- HRMS v16 changes (only playbook evidence so far).
