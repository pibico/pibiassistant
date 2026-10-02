# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""Remove the schema PA Cloud left behind (workflow triggers, tenant credentials).

PA Cloud was retired and AIDA runs natively on the AIDA API, so:

* the DocTypes PA Workflow Trigger, PA Workflow Trigger Filter and PA Workflow
  Trigger Log (cloud-side workflow triggers) were removed from the app;
* PA Chat Settings lost its registration fields (tenant_id, tenant_secret, ...).

On a fresh install none of this exists and the patch does nothing. On an upgraded
site it removes the stale records, never silently:

* every table's row count is logged (and printed in the migrate output);
* a table that still holds rows is dumped to
  ``<site>/private/backups/pa_cloud_leftovers_<doctype>_<timestamp>.json`` before it is
  dropped, and is left untouched when the dump cannot be written;
* a DocType that is not strictly cloud-only is never dropped while it holds rows, it is
  left in place and logged (the list below only has strictly cloud-only DocTypes, the
  rule is kept so a later entry cannot lose data by accident);
* the stale PA Chat Settings values and the encrypted tenant secret are cleared, only the
  names of the fields that held a value are logged, never the values.

Frappe leaves the old PA Chat Settings columns/rows alone on migrate, so no column is
dropped here. The patch is idempotent: a second run finds nothing to do.
"""

import json

import frappe
from frappe.utils import now_datetime

# (DocType, strictly cloud-only). Children and logs first so no link check can trip.
REMOVED_DOCTYPES = (
    ("PA Workflow Trigger Log", True),
    ("PA Workflow Trigger Filter", True),
    ("PA Workflow Trigger", True),
)

SETTINGS = "PA Chat Settings"
REMOVED_SETTINGS_FIELDS = (
    "tenant_id",
    "pa_cloud_url",
    "registration_status",
    "tenant_secret",
    "pending_verification_token",
    "pending_rebind_token",
    "cached_capabilities",
    "capabilities_cached_at",
    "cached_notifications",
)


def execute():
    for doctype, cloud_only in REMOVED_DOCTYPES:
        _remove_doctype(doctype, cloud_only)
    _clear_registration_values()


def _log(message: str) -> None:
    message = f"remove_pa_cloud_leftovers: {message}"
    frappe.logger("migration").info(message)
    print(message)


def _dump_rows(doctype: str) -> str:
    stamp = now_datetime().strftime("%Y%m%d_%H%M%S")
    path = frappe.get_site_path("private", "backups", f"pa_cloud_leftovers_{frappe.scrub(doctype)}_{stamp}.json")
    rows = frappe.db.sql(f"select * from `tab{doctype}`", as_dict=True)
    with open(path, "w") as fh:
        json.dump(rows, fh, default=str, indent=1)
    return path


def _remove_doctype(doctype: str, cloud_only: bool) -> None:
    has_record = bool(frappe.db.exists("DocType", doctype))
    has_table = bool(frappe.db.table_exists(doctype))
    if not has_record and not has_table:
        return

    rows = frappe.db.sql(f"select count(*) from `tab{doctype}`")[0][0] if has_table else 0
    _log(f"{doctype}: {rows} row(s) in its table")

    if rows and not cloud_only:
        _log(f"{doctype}: not strictly cloud-only and holds data, left in place")
        return

    if rows:
        try:
            _log(f"{doctype}: rows saved to {_dump_rows(doctype)}")
        except Exception as e:
            _log(f"{doctype}: could not save the rows ({e!s}), left in place")
            return

    if has_record:
        frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True, ignore_missing=True)
    if has_table:
        frappe.db.sql_ddl(f"drop table `tab{doctype}`")
    _log(f"{doctype}: DocType record and table removed")


def _clear_registration_values() -> None:
    if not frappe.db.exists("DocType", SETTINGS):
        return

    rows = frappe.db.sql(
        "select field, value from `tabSingles` where doctype=%s and field in %s",
        (SETTINGS, REMOVED_SETTINGS_FIELDS),
        as_dict=True,
    )
    held = sorted(r.field for r in rows if r.value not in (None, "", "Not Registered"))
    has_secret = bool(
        frappe.db.sql(
            "select 1 from `__Auth` where doctype=%s and name=%s and fieldname=%s limit 1",
            (SETTINGS, SETTINGS, "tenant_secret"),
        )
    )
    if not rows and not has_secret:
        return

    _log(
        f"{SETTINGS}: {len(rows)} stale value row(s), fields holding a value: {', '.join(held) or 'none'}; "
        f"encrypted tenant secret present: {has_secret}"
    )
    if has_secret:
        frappe.db.sql(
            "delete from `__Auth` where doctype=%s and name=%s and fieldname=%s",
            (SETTINGS, SETTINGS, "tenant_secret"),
        )
    if rows:
        frappe.db.sql(
            "delete from `tabSingles` where doctype=%s and field in %s", (SETTINGS, REMOVED_SETTINGS_FIELDS)
        )
    frappe.clear_document_cache(SETTINGS, SETTINGS)
    _log(f"{SETTINGS}: stale registration values cleared")
