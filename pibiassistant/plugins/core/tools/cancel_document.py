# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


"""Cancel a submitted document."""

from typing import Any, Dict

import frappe

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core.doc_actions import access_error, document_url, fail
from pibiassistant.plugins.query_errors import log_failure


def linked_submitted(doctype: str, name: str) -> list:
    """Submitted documents that depend on this one and would block its cancellation."""
    from frappe.desk.form.linked_with import get_submitted_linked_docs

    found = get_submitted_linked_docs(doctype, name)
    docs = found.get("docs", []) if isinstance(found, dict) else found
    return [d for d in docs or [] if (d.get("doctype") if isinstance(d, dict) else d[0]) != doctype or (d.get("name") if isinstance(d, dict) else d[1]) != name]


def check_cancel(doctype: str, name: str):
    if not doctype or not name:
        return "doctype and name are required"
    if not frappe.db.exists("DocType", doctype):
        return f"DocType '{doctype}' not found"
    if not frappe.get_meta(doctype).is_submittable:
        return f"{doctype} is not submittable, so it has nothing to cancel."
    if not frappe.db.exists(doctype, name):
        return f"{doctype} '{name}' not found"
    status = frappe.db.get_value(doctype, name, "docstatus")
    if status == 0:
        return f"{doctype} '{name}' is a draft; delete it instead of cancelling."
    if status == 2:
        return f"{doctype} '{name}' is already cancelled."
    return None


def preview(arguments: Dict[str, Any]) -> str:
    doctype, name = arguments.get("doctype"), arguments.get("name")
    problem = check_cancel(doctype, name)
    if problem:
        return f"{doctype} '{name}'. Will be refused: {problem}"
    blockers = linked_submitted(doctype, name)
    text = f"Cancel {doctype} '{name}'. It becomes read-only and its accounting or stock entries are reversed."
    if blockers:
        text += f" {len(blockers)} submitted linked document(s) must be cancelled first."
    return text


class DocumentCancel(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "cancel_document"
        self.description = (
            "Cancel a submitted document (docstatus 1), e.g. a Sales Invoice issued by mistake. Reverses its ledger "
            "and stock entries and makes it read-only; it cannot be undone, but amend_document creates a corrected "
            "draft from it. Fails if submitted documents depend on it (payments, delivery notes): cancel those "
            "first. Drafts are deleted, not cancelled. Needs the user's approval."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "A submittable DocType (e.g. 'Sales Invoice')"},
                "name": {"type": "string", "description": "The document name/ID"},
            },
            "required": ["doctype", "name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype, name = arguments.get("doctype"), arguments.get("name")
        problem = check_cancel(doctype, name)
        if problem:
            return fail(problem, doctype=doctype, name=name)
        blocked = access_error(doctype, name, "cancel")
        if blocked:
            return blocked
        try:
            doc = frappe.get_doc(doctype, name)
            if not frappe.has_permission(doctype, "cancel", doc=doc):
                return fail(f"Insufficient permissions to cancel {doctype} '{name}'", doctype=doctype, name=name, permission_error=True)
            blockers = linked_submitted(doctype, name)
            if blockers:
                names = [f"{d['doctype']} {d['name']}" if isinstance(d, dict) else f"{d[0]} {d[1]}" for d in blockers[:10]]
                return fail(
                    f"{doctype} '{name}' cannot be cancelled while these submitted documents depend on it: {', '.join(names)}. Cancel them first.",
                    doctype=doctype, name=name, blocked_by=names,
                )
            doc.cancel()
            frappe.db.commit()
            return {"success": True, "doctype": doctype, "name": name, "docstatus": 2, "url": document_url(doctype, name),
                    "message": f"{doctype} '{name}' cancelled. Use amend_document to create a corrected draft."}
        except frappe.PermissionError:
            return fail(f"Insufficient permissions to cancel {doctype} '{name}'", doctype=doctype, name=name, permission_error=True)
        except Exception as e:
            frappe.db.rollback()
            log_failure("Document Cancel Error", e)
            return fail(str(e) or f"Could not cancel {doctype} '{name}'", doctype=doctype, name=name)


document_cancel = DocumentCancel
