# Roadmap

## M0 — Foundations (done 2026-10-30)
- Repo, pyproject (`uv`), `typer` CLI skeleton, pydantic rule loader, report model, `pytest` + fixtures, CI.
- Rule schema v1, `target.yaml`, rule-coverage test.

## M1 — T-30 static scan (parity with Preflight on v16 frappe/ERPNext core)
- Python `ast` scanner; matchers: import_path, call, hook_key, doctype, doctype_field, select_field, override_subclass, returns_none, undeclared_import.
- Bench/app compatibility rules; `--online` checks.
- Output: text, json, sarif, html, md; `--baseline`; ignore comments.
- Port v16 catalog (frappe + ERPNext) with proof links.

## M2 — Beyond Preflight on scanning
- tree-sitter JS/TS/Vue; Jinja (Print Formats, Email Templates); expression fields.
- Site-saved code scanner incl. Print Formats.
- HRMS + payments + india_compliance rule sets.
- Catalog items marked NEW.

## M3 — T-14 data checks
- Read-only DB connector; `sql_check`, `field_clash`, `site_record`.
- Invalid JSON, extracted-app row counts, clashes, Country code, holiday list assignment gaps.

## M4 — T-7 trial migrate
- Bench wrapper (restore/migrate/tee), copy-only guard, log classifier, clean-twice gate.

## M5 — Frappe app (thin)
- `tminus_app`: Scan/Finding doctypes, enqueue core, dashboard page.

## M6 — T-3 differential
- Snapshot probes (permission matrix, report outputs, list order); diff engine; smoke test runner.

## M7 — T-1 / T-0
- Rehearsal timing, rollback checklist, cutover go/no-go report.

## M8 — Automation
- `fix --apply` codemods (safe rules only), `rules generate`, MCP server for agents.

## Later
- v17 rule set; other frameworks (idea only).

## Open items
- Name availability on PyPI/GitHub/Frappe app name (unchecked).
- Final tagline.
- Verify every catalog entry against framework source before shipping a rule.
