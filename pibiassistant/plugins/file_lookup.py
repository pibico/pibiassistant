"""Pick the File row a caller means when identical uploads share one file_url (Frappe dedupes private files)."""

from typing import Any, Dict, Optional

import frappe

_ROW_FIELDS = ["name", "owner", "attached_to_doctype", "attached_to_name"]


def resolve_file_row(file_url: Optional[str] = None, file_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Best File row for the session user: their own upload, else one they may read, else the first match."""
    filters = {"file_url": file_url} if file_url else {"file_name": file_name} if file_name else None
    if not filters:
        return None
    rows = frappe.get_all("File", filters=filters, fields=_ROW_FIELDS, order_by="creation asc", limit=50)
    if not rows:
        return None
    user = frappe.session.user
    for row in rows:
        if row.owner == user:
            return row
    for row in rows:
        try:
            if frappe.has_permission("File", "read", doc=row.name):
                return row
        except Exception:
            continue
    return rows[0]
