# DEVLOG

Newest first. One entry per working session or logical change. Records what changed in each session.

## Template
```
## YYYY-MM-DD — <short title>
- Commit: <hash or "uncommitted">
- Changed: <repo-relative paths>
- Why: <one line>
- Tests: <what ran, result>
- Open: <anything unfinished or risky>
```

## 2026-10-30 — M1.1 has_permission rule (app-level scanning)
- Commit: uncommitted
- Changed (new): src/tminus/engine/{suppress,paths}.py, engine/matchers/returns_none.py, engine/scanners/hooks.py, rules/v16/{v16-has-permission-hook-returns-none,v16-has-permission-hook-unreadable}.yaml, tests/{test_returns_none,test_hooks_scanner}.py, tests/fixtures/app_bad/, tests/fixtures/app_clean/
- Changed (edited): engine/models.py (HookFunctionMatch, match union, Finding.detail + from_rule), engine/matchers/import_path.py (type guard), engine/scanners/python_ast.py and engine/runner.py (refactored: shared suppress/paths, second pass for hook rules), report/render.py (detail line), tests/test_rule_coverage.py (file + app fixtures), docs/rule-schema.md
- Why: a has_permission hook that can return None now denies access in v16 (silent behaviour; Administrator hides it). Needs hooks.py + the target function, so an app-level pass was added after the per-file pass.
- Tests: 46 passed; ruff, ruff format --check, mypy --strict clean.
- Open: only module-level functions are resolved (not class methods); hooks other than has_permission not covered yet; non-literal hook tables are listed as "not checked".

## 2026-10-30 — M0 skeleton
- Commit: uncommitted
- Changed: pyproject.toml, .gitignore, .github/workflows/ci.yml, src/tminus/{__init__,cli/main,engine/{models,loader,runner},engine/matchers/{__init__,import_path},engine/scanners/python_ast,report/render}.py, src/tminus/rules/v16/{target.yaml,v16-removed-python-stdlib.yaml}, tests/{test_loader,test_import_path,test_rule_coverage,test_cli}.py, tests/fixtures/{violations,clean}.py
- Why: working base for T-30: rule models, YAML loader, import_path matcher (skips try/except ImportError, supports `# tminus: ignore[id]`), `tminus scan` with exit codes 0/1/2/3, text and json output.
- Tests: 24 passed; ruff check, ruff format --check and mypy --strict clean (Python 3.12.3).
- Open: version-gated code (`if frappe.__version__ ...`) not skipped yet; only the import_path matcher exists; starter rule's module list still to verify against Python 3.14 release notes.

## 2026-10-30 — Design docs created and source-verified
- Commit: uncommitted
- Changed: README.md, AGENTS.md, docs/{vision,gap-analysis,architecture,stages,rule-schema,v16-change-catalog,tech-stack,roadmap,source-verification,DECISIONS,DEVLOG}.md
- Why: define T-MINUS (v15 -> v16 upgrade readiness tool) before writing code; catalog cross-checked against the Frappe v16 wiki and Preflight rules page.
- Tests: none (docs only)
- Open: name availability (PyPI/GitHub/Frappe app) unchecked; orphan-doctype data-loss claim disputed between sources; catalog entries still need verification against framework source.
