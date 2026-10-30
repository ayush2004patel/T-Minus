# Tech stack

| Concern | Choice |
|---|---|
| Core language | Python 3.12+ (tool must run next to a v15 bench) |
| Packaging | pyproject.toml, uv, PyPI |
| CLI | typer |
| Python analysis | stdlib ast (detect), libcst (fix) |
| JS/TS/Vue/SCSS | tree-sitter |
| Jinja | jinja2 Environment.parse |
| Rules | YAML + pydantic v2 |
| DB | PyMySQL or mariadb connector, read-only user |
| Runner | subprocess around bench |
| Output | rich, json, SARIF, HTML (jinja2), Markdown |
| Tests | pytest, fixtures, rule-coverage test |
| Lint/types | ruff, mypy |
| CI | GitHub Actions |
| Frappe app | Frappe v15 first, v16-compatible; DocTypes + frappe.enqueue + desk page |
| Runtime tests | Frappe IntegrationTestCase; optional Playwright |
| Agents | AGENTS.md; MCP server later |
