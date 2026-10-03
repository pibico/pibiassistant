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


"""Create the corrected draft of a cancelled document."""

from typing import Any, Dict

import frappe

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core.doc_actions import access_error, document_url, fail
from pibiassistant.plugins.query_errors import log_failure


def check_amend(doctype: str, name: str):
    if not doctype or not name:
        return "doctype and name are required"
    if not frappe.db.exists("DocType", doctype):
        return f"DocType '{doctype}' not found"
    meta = frappe.get_meta(doctype)
    if not meta.is_submittable or not meta.has_field("amended_from"):
        return f"{doctype} cannot be amended."
    if not frappe.db.exists(doctype, name):
        return f"{doctype} '{name}' not found"
    if frappe.db.get_value(doctype, name, "docstatus") != 2:
        return f"{doctype} '{name}' is not cancelled. Only cancelled documents can be amended; use cancel_document first."
    existing = frappe.db.get_value(doctype, {"amended_from": name, "docstatus": ["<", 2]}, "name")
    if existing:
        return f"{doctype} '{name}' was already amended by {existing}."
    return None


def preview(arguments: Dict[str, Any]) -> str:
    doctype, name = arguments.get("doctype"), arguments.get("name")
    problem = check_amend(doctype, name)
    if problem:
        return f"{doctype} '{name}'. Will be refused: {problem}"
    return f"Create a new draft of {doctype} '{name}' (amended copy) so it can be corrected and submitted again."


class DocumentAmend(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "amend_document"
        self.description = (
            "Amend a cancelled document: creates a new draft copy linked to it (amended_from) with a name like "
            "'SINV-0001-1', ready to be corrected with update_document and submitted again with submit_document. "
            "Only for cancelled documents (see cancel_document); one amendment per cancelled document. "
            "Needs the user's approval."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "A submittable DocType (e.g. 'Sales Invoice')"},
                "name": {"type": "string", "description": "The name/ID of the CANCELLED document"},
            },
            "required": ["doctype", "name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype, name = arguments.get("doctype"), arguments.get("name")
        problem = check_amend(doctype, name)
        if problem:
            return fail(problem, doctype=doctype, name=name)
        blocked = access_error(doctype, name, "amend")
        if blocked:
            return blocked
        try:
            source = frappe.get_doc(doctype, name)
            if not frappe.has_permission(doctype, "amend", doc=source) and not frappe.has_permission(doctype, "create"):
                return fail(f"Insufficient permissions to amend {doctype} '{name}'", doctype=doctype, name=name, permission_error=True)
            amended = frappe.copy_doc(source, ignore_no_copy=False)
            amended.amended_from = name
            amended.docstatus = 0
            amended.insert()
            frappe.db.commit()
            return {"success": True, "doctype": doctype, "amended_from": name, "name": amended.name, "docstatus": 0,
                    "url": document_url(doctype, amended.name),
                    "message": f"Draft {amended.name} created from cancelled {name}. Correct it and submit it."}
        except frappe.PermissionError:
            return fail(f"Insufficient permissions to amend {doctype} '{name}'", doctype=doctype, name=name, permission_error=True)
        except Exception as e:
            frappe.db.rollback()
            log_failure("Document Amend Error", e)
            return fail(str(e) or f"Could not amend {doctype} '{name}'", doctype=doctype, name=name)


document_amend = DocumentAmend
