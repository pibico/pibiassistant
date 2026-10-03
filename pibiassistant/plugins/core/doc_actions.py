"""Checks shared by the document-lifecycle tools (cancel, amend, create-from, assign, comment)."""

from typing import Any, Dict, Optional

import frappe


def access_error(doctype: str, name: str, perm_type: str) -> Optional[Dict[str, Any]]:
    """The tool result to return when the DocType is closed to this action at the PA layer, else None."""
    from pibiassistant.core.security_config import validate_document_access

    result = validate_document_access(user=frappe.session.user, doctype=doctype, name=name or "", perm_type=perm_type)
    return None if result.get("success") else result


def fail(message: str, **extra) -> Dict[str, Any]:
    return {"success": False, "error": message, **extra}


def document_url(doctype: str, name: str) -> str:
    return frappe.utils.get_url_to_form(doctype, name)
