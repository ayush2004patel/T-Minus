# Vision

## Problem
A major Frappe/ERPNext upgrade fails in four different ways (BWH playbook):

| Category | Meaning |
|---|---|
| Data | A patch reads rows that were always wrong; nothing read them before |
| Loud code | Imports/hooks fail during migrate and give a traceback |
| Quiet code | Fails only when a user opens the page; migrate exits 0 |
| Silent behaviour | Runs fine and now does something different |

Existing tooling covers one slice: a static API scanner finds some loud and quiet code.
Nothing covers data, the migrate log, or silent behaviour, and nothing ties the steps together.

## Goal
One tool that follows the whole upgrade timeline and tells a developer, per stage, whether they are ready.

## Principles
1. Read-only by default; mutation is opt-in and explicit.
2. A clean report means "no known problems", never "safe". Say what was not checked.
3. Rules are data, each with a proof link.
4. Cover custom apps, not just frappe/erpnext: hrms, payments, india_compliance and your own apps.
5. Findings are categorised (data / loud / quiet / silent) so effort goes to the right place.
6. Version-agnostic engine; v16 is the first rule set, v17 should need rules only.

## Non-goals (v1)
- Other frameworks (long-term idea only).
- Upgrading production automatically.
- Replacing human judgement on business data (e.g. whether a tax rate should be 5% or 18%).
