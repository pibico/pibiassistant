# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""
Linked Documents Tool for Core Plugin.
Finds the documents that reference a given document (the Sales Order made from a
Quotation, the payments against an invoice) using Frappe's own link resolution.
"""

from typing import Any, Dict

import frappe
from frappe import _

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.limits import clamp_limit

MAX_PER_DOCTYPE = 50
MAX_TOTAL = 200


class GetLinkedDocuments(BaseTool):
    """List documents that link to a document, grouped by DocType, honouring permissions."""

    def __init__(self):
        super().__init__()
        self.name = "get_linked_documents"
        self.description = (
            "Find the documents linked to a specific document: for a Quotation the Sales Orders "
            "created from it, for a Sales Invoice its Payment Entries and Delivery Notes, for a "
            "Customer its invoices and orders. Use this instead of list_documents on child tables "
            "(e.g. 'Sales Order Item'), which are not directly listable. Only documents the user "
            "may read are returned, grouped by DocType."
        )
        self.requires_permission = None

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "DocType of the document, e.g. 'Quotation'."},
                "name": {"type": "string", "description": "Name of the document, e.g. 'SAL-QTN-2024-00001'."},
                "linked_doctype": {
                    "type": "string",
                    "description": "Optional: return only links from this DocType, e.g. 'Sales Order'.",
                },
                "limit": {
                    "type": "integer",
                    "default": MAX_PER_DOCTYPE,
                    "maximum": MAX_PER_DOCTYPE,
                    "description": "Maximum documents returned per linked DocType.",
                },
            },
            "required": ["doctype", "name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        name = arguments.get("name")
        only = arguments.get("linked_doctype")
        per_type = clamp_limit(arguments.get("limit"), MAX_PER_DOCTYPE, MAX_PER_DOCTYPE)

        if not doctype or not name:
            return {"success": False, "error": "doctype and name are required"}

        from pibiassistant.core.security_config import filter_sensitive_fields, validate_document_access

        validation = validate_document_access(
            user=frappe.session.user, doctype=doctype, name=name, perm_type="read"
        )
        if not validation["success"]:
            return validation
        user_role = validation["role"]

        if not frappe.db.exists(doctype, name):
            return {"success": False, "error": f"{doctype} '{name}' not found"}

        try:
            from frappe.desk.form.linked_with import get_linked_doctypes, get_linked_docs

            linkinfo = get_linked_doctypes(doctype)
            if only:
                linkinfo = {k: v for k, v in linkinfo.items() if k == only}
            found = get_linked_docs(doctype, name, linkinfo)
        except Exception as e:
            frappe.log_error(title=_("Linked Documents Error"), message=f"{doctype} '{name}': {e}")
            return {"success": False, "error": str(e)}

        linked: Dict[str, list] = {}
        total = 0
        truncated = False
        for linked_doctype, rows in sorted(found.items()):
            kept = []
            for row in rows:
                if len(kept) >= per_type or total >= MAX_TOTAL:
                    truncated = True
                    break
                kept.append(filter_sensitive_fields(dict(row), linked_doctype, user_role))
                total += 1
            if kept:
                linked[linked_doctype] = kept

        result = {
            "success": True,
            "doctype": doctype,
            "name": name,
            "total_linked": total,
            "linked": linked,
        }
        if truncated:
            result["truncated"] = True
        return result


get_linked_documents = GetLinkedDocuments
