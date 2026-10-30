# AGENTS.md — rules for coding agents working on or with T-MINUS

## Working on T-MINUS itself
1. Rules are data (`rules/<target>/*.yaml`). Adding a rule must never need an engine change; if it does, extend a match type instead.
2. Every rule needs: a source reference, a violation fixture, a clean fixture. `tests/test_rule_coverage.py` fails otherwise.
3. Verify each claim against framework source or a merged PR before writing the rule. Do not rely on memory.
4. Core must not import `frappe`. Anything needing live Frappe lives in `tminus_app`.
5. Work from the user's latest provided code. No full rewrites when a surgical change suffices.

## Using T-MINUS to upgrade a site
1. Never run against production. Only a restored copy; if the site cannot be identified, stop and ask.
2. Data fixes happen on v15, followed by a fresh backup. Never fix only the restored copy.
3. Never delete rows to make a patch pass. Write the script, explain it, stop for human review.
4. Never edit `apps/frappe`, `apps/erpnext`, `apps/hrms`. Fix the custom app.
5. One commit per fix, naming the v16 change behind it.
6. Port code, do not redesign it. Behaviour must stay the same.
7. A clean exit code is not a clean migration: always read the whole log (`tminus trial` does this).
8. Report what could not be fixed. A silent guess is worse than an open question.

## Project history
- Design decisions go into `docs/DECISIONS.md`; a short entry per work session goes into `docs/DEVLOG.md`.
- Work from the latest code in the repo (or the version the user pastes), not from earlier generated output.
- Keep code comments to short one-liners; every new function gets one.
