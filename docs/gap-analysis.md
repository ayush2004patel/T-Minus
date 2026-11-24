# Capability gaps

T-MINUS v1.0.1 is a focused, read-only T-30 scanner. Its rules are verified against Frappe,
ERPNext and HRMS source, the Frappe v16 migration documentation, and the BWH *ERPNext Upgrade
Playbook*. This document records the upgrade risks that need a later stage rather than pretending
that a source scan can prove them safe.

## Current v1.0.1 coverage

- YAML rules with source references, violation fixtures and clean fixtures.
- Python, JavaScript, standard print-format templates, hooks, SQL text and app-packaging scans.
- Baselines, targeted suppressions, CI exit codes, and text, JSON, HTML, PDF and SARIF reports.
- Static checks for known framework, ERPNext and HRMS compatibility changes.

## Planned capability gaps

| Gap | Why source scanning cannot settle it | Planned stage |
|---|---|---|
| Invalid or upgrade-sensitive site data | Values live in the database, not in an app folder. | T-14 data checks |
| Removed-DocType data survival | A real migration on a restored copy is needed to compare tables before and after migration. | T-7 trial |
| Custom-field clashes with target standard fields | Requires the site's Custom Field records. | T-14 data checks |
| Saved Server Scripts, Client Scripts and customisations | These are stored in the site database. | T-14 data checks |
| Permission and ordering behaviour | Static code cannot prove runtime behaviour for real users and real data. | T-3 differential checks |
| Migration warnings and partial failures | Only a complete `bench migrate` log on a restored site can show them. | T-7 trial |
| Safe automated changes | Compatibility fixes need explicit review before any mutation. | Future codemods |
| Rehearsal timing, rollback and cutover decisions | These are operational decisions, not source findings. | T-1 and T-0 |

## Candidate checks requiring source verification

Potential rules remain candidates until verified against framework source or a merged upstream
change. Examples include changed transaction behaviour, single-DocType value types, report and
page JavaScript loading, POST-only methods, cache argument restrictions, field defaults, virtual
fields, translations and country-code validation.
