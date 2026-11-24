# Changelog

## 1.0.1 (2026-11-24)

Release maintenance update following v1.0.0.

## 1.0.0 (2026-11-21)

First release: the T-30 static scanner for Frappe/ERPNext v15 → v16.

- `tminus scan`: Python, JavaScript, Jinja print formats, `hooks.py`, SQL text and app
  packaging checks; text, JSON, HTML, PDF and SARIF reports; `--fail-on`; `--baseline` / `--write-baseline`;
  `# tminus: ignore[rule-id]` comments.
- `tminus env`: compare Python, Node, MariaDB and Redis on this machine with what v16 needs.
- 25 rules, each a YAML file with its evidence, checked against frappe, erpnext and hrms
  version-15 and version-16 source.
