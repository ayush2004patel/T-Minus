# v15 → v16 change catalog

Sources: **W** = Frappe wiki *Migrating to version 16*; **P** = BWH *ERPNext Upgrade Playbook*.
Category = data / loud / quiet / silent. Entries are source material for future rules and must be
verified against framework source or a merged upstream change before implementation.

## Environment

| Change | Cat | Src |
|---|---|---|
| Python 3.14, Node 24, MariaDB 10.6+ (11.8 recommended), Redis 6+ | loud | W, P |
| Python removed `imghdr`, `cgi`, `imp`, `telnetlib`, `crypt` and `pipes` | loud | P |
| Packages no longer installed by Frappe must be declared by the app | loud | W |
| `bench version` default output format changed from `legacy` to `plain` | quiet | W |

## Framework and extracted applications

| Change | Cat | Src |
|---|---|---|
| Energy Points, Newsletter, Blog and backup integrations moved to separate apps | data | W, P |
| Transaction Log and its report were removed | data | W, P |
| GeoIP (MaxMind) was removed | loud | W |
| `has_permission` returning `None` denies access | silent | W, P |
| `override_doctype_class` must subclass the original controller | loud | W, P |

## Database and ORM

| Change | Cat | Src |
|---|---|---|
| Default sort changed from `modified` to `creation` | silent | W, P |
| SQL functions in `get_all` / `get_list` fields require supported query syntax | quiet | W, P |
| Single-DocType values returned by `db.get_value` are typed | silent | W, P |
| `db.commit()` in document hooks is unsupported | silent | W, P |
| `get_doc(dt, name, field=value)` no longer updates values | silent | W |
| `!= None` filters now generate `IS NOT NULL` | silent | W |
| Virtual fields are excluded by `meta.get_valid_columns()` | silent | W |
| Country requires a valid ISO 3166 alpha-2 code | data | W |

## Client, templates and tests

| Change | Cat | Src |
|---|---|---|
| `/app` changed to `/desk` | silent | W, P |
| Standard workspace edits can be lost during migration | data | W |
| Reports, Dashboard Charts and Pages use IIFE JavaScript loading | silent | W |
| `logout`, `web_logout`, `upload_file` and `send_login_link` require POST | loud | W |
| Translation hooks and helper functions were removed or changed | loud | W |
| `FrappeTestCase` is deprecated in favour of integration or unit test classes | quiet | W |

## ERPNext and HRMS

| Change | Cat | Src |
|---|---|---|
| Item-wise tax details moved from JSON to a child table | data | P |
| Frozen-account settings moved to Company | loud | P |
| Asset, Purchase Order Item, UTM and tax-withholding APIs changed | loud | P |
| Extracted-application DocType names hard-coded in links or strings can fail | quiet | P |
| v16 uses Holiday List Assignment rather than `Employee.holiday_list` | silent | P |
| Employee benefit helpers such as `get_max_benefits` were removed | quiet | P |

## Process findings

- Fix data on v15, take a fresh backup, and rehearse only on a restored copy.
- Never delete rows merely to pass a patch; write and review a data-fix script.
- Test permissions as a normal user because Administrator can bypass permission checks.
- Preserve the v15 bench and final backup for rollback.

## Reference PRs

EPS #32040, Newsletter #32971, Backup integrations #32351, Blog #32737, Transaction Log #33844,
`has_permission` None #24253, `raise_exception` #24266, `override_doctype` #26152,
translations #22962, query builder #32381, JavaScript IIFE #33973, map view #32207,
`bench version` #33621, virtual fields #27553, time field #33515, `!= None` #34207 and
`in_test` #32960.
