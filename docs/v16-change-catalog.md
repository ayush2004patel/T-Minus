# v15 → v16 change catalog

Sources: **W** = Frappe wiki "Migrating to version 16"; **P** = BWH Upgrade Playbook; **PF** = Preflight rules page.
Category = data / loud / quiet / silent. "NEW" = no Preflight rule found. Verify each item against source before turning it into a rule.

## Environment
| Change | Cat | Src |
|---|---|---|
| Python 3.14, Node 24, MariaDB 10.6+ (11.8 recommended), Redis 6+ | loud | W, P |
| Python 3.14 removed `imghdr cgi imp telnetlib crypt pipes`; `distutils`, `ast.Str` etc. | loud | P, PF |
| rq 2: `Connection` removed | loud | P, PF |
| `pkg_resources` unavailable in a fresh env | loud | PF |
| Packages no longer installed by frappe: bleach, boto3, botocore, s3transfer, dropbox, maxminddb-geolite2, maxminddb, cairocffi, posthog — declare them yourself | loud | PF, W |
| `bench version` default output format `legacy` → `plain` (scripts parsing it break) | quiet | W (NEW) |

## Removed from framework / extracted apps (data loss risk)
| Change | Cat | Src |
|---|---|---|
| Energy Points → `frappe/eps`; Newsletter → `frappe/newsletter`; Blog → `frappe/blog`; Backup integrations → `frappe/offsite_backups` | data | W, P, PF |
| Orphan doctypes of extracted apps: **sources disagree**. P says migrate drops them and the data goes with them; PF says the tables survive and only ORM reads fail (`DoesNotExistError` / `ImportError`). Treat as unverified until `tminus trial` compares tables before/after migrate | data | P vs PF |
| Transaction Log + report removed, no replacement app | data | W, P |
| Changelog Feed / What's New panel removed | loud | PF |
| GeoIP (MaxMind) removed | loud | W |
| `leaderboards` hook, `frappe.views.ListSidebar` removed | loud | PF |

## Permissions
| Change | Cat | Src |
|---|---|---|
| `has_permission` hook returning None now denies (admin bypasses, so only non-admin tests see it) | silent | W, P, PF |
| `raise_exception` arg of `has_permission` removed (use `print_logs`) | loud | W, PF |
| System Console only for Administrator by default | silent | W (NEW) |
| `override_doctype_class` must subclass the original controller (wiki heading calls the hook `override_doctype`) | loud | W, P, PF |

## Database / ORM
| Change | Cat | Src |
|---|---|---|
| Default sort `modified` → `creation` for `get_all/get_list/db.get_value(s)/qb.get_query`; DocType `sort_field` should be changed to `creation` (the `modified` index is then dropped on migrate; re-add with `frappe.db.add_index` in `on_doctype_update`). PF deliberately has no rule | silent | W, P |
| `get_all/get_list` use the query builder; SQL functions as strings (`"sum(qty) as qty"`) must become dict syntax or `frappe.qb` | quiet | W, P, PF |
| `db.get_value` on single doctypes returns typed values (`== "1"` → `== 1`) | silent | W, P (NEW) |
| `db.commit()` in document hooks unsupported; writes roll back | silent | W, P (NEW) |
| `frappe.sendmail(now=True)` no longer commits | silent | W (NEW) |
| `get_doc(dt, name, field=value)` no longer updates values | silent | W (NEW) |
| `db.value_cache` nested; `db.count(cache=True)` uses value_cache | quiet | W, PF |
| `!= None` filter now generates `IS NOT NULL` | silent | W (NEW) |
| `meta.get_valid_columns()` excludes virtual fields | silent | W (NEW) |
| `site_cache` rejects unhashable args | loud | W (NEW) |
| Time field no default unless options "Now" | silent | W (NEW) |
| Country requires valid ISO 3166 alpha-2 `code` | data | W (NEW) |
| Site config and common_site_config cached up to 1 minute | silent | W (NEW) |

## Client / desk
| Change | Cat | Src |
|---|---|---|
| `/app` → `/desk`; client code matching `/app/` URLs silently stops | silent | W, P (NEW as JS rule) |
| Apps page `/apps` deprecated; custom apps need `add_to_apps_screen` | quiet | W, PF |
| Edits to standard workspaces (e.g. Buying, Selling) are lost on migrate; back up via Copy to Clipboard | data | W |
| Public workspace made in v15 has no module (not listed in navigation); private workspaces only under My Space (setting off for all users); public workspace in a custom module is on no app rail; app with workspaces but no `add_to_apps_screen` gets no Apps-screen tile | silent | PF (site records) |
| New Workspace Sidebar doctype, desktop screen, My Workspaces icon; curate a standard sidebar for your app | info | W |
| JS of Reports, Dashboard Charts, Pages evaluated as IIFEs (global leaks break) | silent | W (NEW) |
| `logout`, `web_logout`, `upload_file`, `send_login_link` require POST | loud | W (NEW) |
| Octicons stylesheet and icon font removed in v16.50.0 (`bench build` fails on import; `octicon` class renders blank) | quiet | PF |
| List sidebar removed; saved filters now above the list; quick filters chosen per user in list view | quiet | PF, W |
| Map view behaves like list view | info | W |
| Awesome bar/notifications/user settings moved to sidebar | info | W |

## Translations, HTML, tests
| Change | Cat | Src |
|---|---|---|
| `get_translated_dict` hook removed (view-specific translations; move to app translation files; web forms keep a small label dict); `frappe.get_lang_dict`, `translate.get_dict`, `get_lang_js`, `get_dict_from_hooks` removed; `doc.meta.__messages` no longer holds doc-specific translations; currency codes and timezone names no longer translated; `country_info.get_translated_dict` deprecated, use `get_translated_countries` | loud | W (NEW; PF covers only the country_info deprecation) |
| `sanitize_html` uses nh3: forbidden tags stripped not escaped | silent | W, PF |
| `FrappeTestCase` deprecated (removed in v17) → `IntegrationTestCase` (DB) / `UnitTestCase` (in-memory), import from `frappe.tests`; `test_dependencies` → `EXTRA_TEST_RECORD_DEPENDENCIES`; `test_ignore` → `IGNORE_TEST_RECORD_DEPENDENCIES`; `frappe.flags.in_test` → `frappe.in_test` (set via `frappe.tests.utils.toggle_test_mode`); overridden `setUpClass` must call `super()` | quiet | W, PF |
| Server Script requests to private addresses refused | loud | PF |

## ERPNext
| Change | Cat | Src |
|---|---|---|
| Item-wise tax details JSON → child table; invalid `item_tax_rate` text crashes ERPNext patch | data | P, PF |
| Frozen accounts settings moved from Accounts Settings to Company (`acc_frozen_upto` → `accounts_frozen_till_date`, `frozen_accounts_modifier` → `role_allowed_for_frozen_entries`); default manufacturing warehouses moved to Company; `post_change_gl_entries` moved to POS Settings (`get_single_value` on old field raises) | loud | P, PF |
| Asset `gross_purchase_amount` → `net_purchase_amount`; custom field with same name duplicates on form | quiet | P, PF |
| Purchase Order Item `subcontracted_quantity` → `subcontracted_qty` | quiet | P, PF |
| `source`/`campaign` → `utm_source`/`utm_campaign`; Lead Source/Marketing Campaign → UTM Source/Campaign; old columns not copied | silent | P, PF |
| Tax withholding rebuilt around Tax Withholding Entry; ~20 helpers removed | loud | P, PF |
| `get_batch_incoming_rate` removed; `get_item_tax_map`, `get_itemised_tax`, `validate_party_frozen_disabled` signatures changed | loud | P |
| Closing Stock Balance → Stock Closing Entry; Homepage settings removed; Repost settings merged; scrap items → secondary items; replaced reports; workstation cost table; Budget model; POS fields | loud/quiet | PF |
| Repost Allowed Types left unchecked on v15 are treated as allowed on v16 | silent | PF |
| `advance_payment_doctypes` hook replaced by receivable/payable hooks | silent | PF |
| Extracted-app doctype names hard-coded in links/strings fail when the form opens | quiet | P |

## HRMS
| Change | Cat | Src |
|---|---|---|
| v16 reads Holiday List Assignment, ignores `Employee.holiday_list`; patch skips left employees and logs nothing | silent | P |
| Employee benefit helpers (`get_max_benefits`) removed; use `get_salary_structure_assignment` | quiet | P |
| No official v16 migration guide: diff `version-15..version-16` | — | P |

## Process findings (not code)
- Fix data on v15, fresh backup, re-restore. Never delete rows to pass a patch. Port code, do not redesign it.
- Administrator hides permission bugs; smoke test as a normal user.
- Keep v15 bench and final backup untouched for rollback; old bench for a month.


## Additional items found in the Preflight rule list (re-read 2026-10-30)
Not in the sections above. All PF unless noted; verify against framework source before turning into rules.

### Framework removals / moves (loud)
- `frappe.test_runner` suite helpers (`run_all_tests`, `run_tests_for_doctype`, ...) removed; use `bench run-tests`.
- `frappe.config` helpers moved to `frappe.utils.modules`.
- `get_allowed_pages`, `get_allowed_reports`, `get_allowed_report_names`, `get_user_pages_or_reports` in `frappe.boot` moved to `DeskViews` (`frappe.desk.desk_views`).
- `frappe.desk.desktop.get_workspace_sidebar_items` (endpoint and import) removed; use `get_workspaces` / `frappe.boot.workspaces`.
- `frappe.core.doctype.user.user.get_roles` endpoint and import removed; use `frappe.get_roles(user)`.
- `frappe.utils.xlsxutils.get_excel_date_format` removed; `make_xlsx` takes an xlsxwriter workbook (not openpyxl); `build_xlsx_data` returns three values (unpacking two raises `ValueError`).
- `frappe.boot.changelog_feed`, `frappe.boot.marketplace_apps`, `frappe.search.utils.get_marketplace_apps` and the `get_changelog_feed` hook gone with the What's New panel.
- Changelog Feed doctypes removed (v16.50.0).

### Behaviour changes (silent)
- `build_xlsx_data(include_filters=...)` reads filter rows from `data.applied_filters` (v16.17.0).
- Gravatar helpers return an identicon or empty string (already so in v15.112.0).

### Deprecated, removal in v17 (warnings)
`frappe.client.get_js`, `email_queue.send_mail`, `get_number_format_info`, gzip helpers in `frappe.utils`, `frappe.utils.make_esc`, `read_multi_pdf`, `show_progress` in bulk update, `frappe.db.is_column_missing` (renamed), `frappe.get_test_records`, helpers re-exported by `frappe.test_runner` (import from `frappe.tests.utils`), helpers on `frappe.tests.utils`, system-settings test helpers.

### ERPNext
- Removed with no replacement: Payment Entry `get_party_and_account_balance`, Bank Account `make_bank_account`, Pricing Rule `make_pricing_rule`; JS `erpnext.utils.make_pricing_rule` (use `frappe.new_doc("Pricing Rule", ...)`, works on both).
- POS Closing Entry `get_pos_invoices` → `get_invoices`; tax `rate` and `pos_transactions` table → `pos_invoices`; POS Profile `disable_grand_total_to_default_mop` inverted to `set_grand_total_to_default_mop`.
- Asset Repair `get_repair_cost_for_purchase_invoice` → `get_unallocated_repair_cost`; seven depreciation helpers renamed/replaced; `make_depreciation_entry` args: `asset_depr_schedule_name` → `depr_schedule_name`, `credit_and_debit_accounts` and `depreciation_cost_center_and_depreciation_series` removed.
- Sales Order `make_purchase_order_for_default_supplier`, Material Request `get_default_supplier_query` removed; funnel `get_opp_by_lead_source` → `get_opp_by_utm_source`.
- Budget `fiscal_year`, `monthly_distribution` replaced (a Budget covers one account over a range of fiscal years).
- Removed fields with no replacement on Company, Customer, Item, Payment Entry, Job Card, Journal Entry (exact list: read PF rule data).
- Scrap fields of BOM, Stock Entry Detail, Subcontracting Receipt Item → secondary-item fields; Serial No `purchase_document_no` → `reference_name`; Workstation/Workstation Type hourly rates → `workstation_costs` table.
- TDS fields on purchases/payments (e.g. Purchase Order `apply_tds`) replaced; Advance Tax, Tax Withheld Vouchers, TDS/TCS functions of Tax Withholding Category replaced by Tax Withholding Entry.
- Replaced reports: Employee Billing Summary, Project Billing Summary, BOM Stock Report, BOM Stock Calculated, Supplier-Wise Sales Analytics.
- Old columns of migrated fields stay: `get_all`/`db.get_value` return the value at upgrade time, `get_list` omits the field.

## Reference PRs (from the wiki)
EPS #32040, Newsletter #32971, Backup integrations #32351, Blog #32737, Transaction Log #33844, `has_permission` None #24253, `raise_exception` #24266, `override_doctype` #26152, translations #22962, query builder #32381 (+ erpnext #50550, hrms #3273 / #3741, lending #728), JS IIFE #33973, map view #32207, `bench version` #33621, virtual fields #27553, time field #33515, `!= None` #34207, `in_test` #32960.

## Source freshness
- Frappe wiki page: last edited 2026-08-17 (31 revisions).
- Preflight rules: last checked 2026-10-25 against frappe v16.53.0.
- BWH playbook: PDF as provided (v15 → v16).
