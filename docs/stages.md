# Countdown stages

| Stage | Question answered | Inputs | Output |
|---|---|---|---|
| T-30 `scan` | Will the code and bench install and import on the target? | `--site` or `--path`, `--target` | Findings by rule, "not checked" list |
| T-14 `data` | Is the data safe for the target's patches and removals? | read-only DB | Invalid rows, row counts at risk, clashing custom fields |
| T-7 `trial` | Does migrate really succeed? | restored copy on a v16 bench | Classified log findings, per-run diff, "clean twice" counter |
| T-3 `diff` | Does the site behave the same? | v15 + v16 snapshots | Permission matrix diff, report-number diff, list-order diff, smoke results |
| T-1 `rehearse` | How long will cutover take, and can we roll back? | fresh backup | Timed steps, rollback checklist |
| T-0 `cutover` | Go / no-go | all previous results | Checklist with named owner, window, rollback trigger |

## Gate rules
- T-7 passes only when migrate is clean **twice in a row** on a fresh restore, with the whole log read.
- T-3 smoke tests run as a non-Administrator user (Administrator bypasses permissions).
- T-1 requires a dry run on a backup taken after the last data fix.
- T-0 requires: window, named decision maker, failure definition, post-cutover data-loss statement.

## T-30 checks
Python/node/MariaDB/Redis versions; each app's `requires-python`, frappe bound, dependency pins, `required_apps`, target branch (`--online`), dependency wheels (`--online`); code in custom apps, patches, hooks; site-saved code; customisations.

## T-14 checks
- Invalid JSON in `item_tax_rate` across Sales Invoice/Sales Order/Delivery Note/Quotation and purchase-side item tables.
- Row counts for Blog Post, Newsletter, Energy Point Log, S3 Backup Settings, Dropbox Settings, Transaction Log. Whether that data is dropped or survives migrate is disputed between sources; treat any non-zero count as at risk until T-7 proves otherwise.
- Custom fields whose name equals a new standard field on the target.
- Repost Allowed Types left unchecked; Country without valid ISO code; Employee holiday lists without Holiday List Assignment.
- Hard-coded references to extracted doctypes.

## T-7 log classification
Record the table list before and after migrate and report extracted-app tables that disappeared; grep `skipping|warning|error|traceback`; treat "Skipping fixture syncing ... ImportError" as an error even when exit code is 0; classify each hit as data, loud code, quiet code or silent behaviour; link to the rule that predicts it.

## T-3 differential
- Permission matrix: per role x doctype x ptype, via `has_permission`, on both versions.
- Reports: run each custom report with fixed filters, diff totals.
- Lists: record order for `get_all` call sites flagged by the sort heuristic.
- Smoke: open list/form/report of each customised doctype, save/submit one doc per daily doctype, as a normal user; check Error Log and failed scheduler jobs.
