"""Row-level read check for DocTypes whose access is decided by a has_permission hook (File, ...)."""

from typing import Any, Dict, List

import frappe


def has_row_permission_hook(doctype: str) -> bool:
    """True when the DocType's read access depends on the individual row, not just its role permission."""
    return bool(frappe.get_hooks("has_permission").get(doctype)) or doctype == "File"


def drop_unreadable_rows(doctype: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only rows the session user may read. Rows without a name are kept: nothing to check."""
    if not has_row_permission_hook(doctype):
        return rows
    kept = []
    for row in rows:
        name = row.get("name") if isinstance(row, dict) else None
        if name is None or frappe.has_permission(doctype, "read", doc=name):
            kept.append(row)
    return kept
