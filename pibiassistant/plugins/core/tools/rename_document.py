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

"""
Document Rename Tool for Core Plugin.
Renames a document (its name/ID) and lets Frappe update every reference to it.
"""

from typing import Any, Dict

import frappe

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.query_errors import log_failure

# Renaming these changes logins, accounting trees, schema or code paths: done in the Desk, never here.
RENAME_BLOCKED_DOCTYPES = frozenset({"User", "Company", "DocType", "Module Def", "Page", "Report", "Workspace"})
MAX_NAME_LENGTH = 140


def count_references(doctype: str, name: str) -> int:
    """Documents that point at ``name`` through Link fields or Dynamic Links (what a rename would rewrite)."""
    from frappe.model.rename_doc import get_link_fields

    total = 0
    for link in get_link_fields(doctype):
        try:
            if frappe.get_meta(link.parent).issingle:
                continue
            total += frappe.db.count(link.parent, {link.fieldname: name})
        except Exception:
            continue
    total += frappe.db.count("Dynamic Link", {"link_doctype": doctype, "link_name": name})
    return total


def check_rename(doctype: str, name: str, new_name: str) -> str | None:
    """Reason a rename must not go ahead, or None. Runs before the approval card and again at execution."""
    if not doctype or not name or not isinstance(new_name, str) or not new_name.strip():
        return "doctype, name and new_name are required"
    new_name = new_name.strip()
    if len(new_name) > MAX_NAME_LENGTH:
        return f"new_name is longer than {MAX_NAME_LENGTH} characters"
    if new_name == name:
        return "new_name is the same as the current name"
    if not frappe.db.exists("DocType", doctype):
        return f"DocType '{doctype}' not found"
    if doctype in RENAME_BLOCKED_DOCTYPES:
        return f"{doctype} cannot be renamed through the assistant. Do it in the Desk."

    from pibiassistant.core.security_config import PRIVILEGE_DOCTYPES

    if doctype in PRIVILEGE_DOCTYPES:
        return f"{doctype} cannot be renamed through the assistant. Do it in the Desk."

    meta = frappe.get_meta(doctype)
    if not meta.allow_rename:
        return f"{doctype} does not allow renaming (Allow Rename is off for this DocType)."
    if meta.issingle:
        return f"{doctype} is a single DocType and has no name to change."
    if not frappe.db.exists(doctype, name):
        return f"{doctype} '{name}' not found"
    if frappe.db.exists(doctype, new_name):
        return f"{doctype} '{new_name}' already exists. Merging documents is not supported here."
    if meta.is_submittable and frappe.db.get_value(doctype, name, "docstatus") != 0:
        return f"{doctype} '{name}' is submitted or cancelled and cannot be renamed."
    return None


def preview(arguments: Dict[str, Any]) -> str:
    doctype, name, new_name = arguments.get("doctype"), arguments.get("name"), arguments.get("new_name")
    problem = check_rename(doctype, name, new_name)
    if problem:
        return f"{doctype} '{name}' -> '{new_name}'. Will be refused: {problem}"
    return (
        f"{doctype}: '{name}' -> '{str(new_name).strip()}'. "
        f"{count_references(doctype, name)} reference(s) in other documents will be updated."
    )


class DocumentRename(BaseTool):
    """Rename an existing document; Frappe rewrites every Link and Dynamic Link that points at it."""

    def __init__(self):
        super().__init__()
        self.name = "rename_document"
        self.description = (
            "Rename an existing Frappe document (change its name/ID, e.g. a Contact or Customer). "
            "Only DocTypes with Allow Rename can be renamed; submitted documents, users, companies and "
            "permission DocTypes cannot, and merging into an existing name is not supported. Every reference "
            "to the document in other documents is updated automatically. This is a write action that needs "
            "the user's approval. To change a field such as first_name use update_document instead."
        )
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "The DocType (e.g. 'Contact', 'Customer', 'Item')"},
                "name": {"type": "string", "description": "The current name/ID of the document"},
                "new_name": {"type": "string", "description": "The new name/ID (max 140 characters)"},
            },
            "required": ["doctype", "name", "new_name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        name = arguments.get("name")
        new_name = arguments.get("new_name")

        problem = check_rename(doctype, name, new_name)
        if problem:
            return {"success": False, "error": problem, "doctype": doctype, "name": name}
        new_name = new_name.strip()

        from pibiassistant.core.security_config import validate_document_access

        validation = validate_document_access(user=frappe.session.user, doctype=doctype, name=name, perm_type="write")
        if not validation["success"]:
            return validation

        try:
            if not frappe.has_permission(doctype, "write", doc=name):
                return {
                    "success": False,
                    "error": f"Insufficient permissions to rename {doctype} '{name}'",
                    "doctype": doctype,
                    "name": name,
                    "permission_error": True,
                }
            references = count_references(doctype, name)
            renamed = frappe.rename_doc(doctype, name, new_name, force=False, merge=False, show_alert=False)
            frappe.db.commit()
            return {
                "success": True,
                "doctype": doctype,
                "old_name": name,
                "new_name": renamed,
                "references_updated": references,
                "message": f"{doctype} '{name}' renamed to '{renamed}'",
            }
        except frappe.PermissionError:
            return {
                "success": False,
                "error": f"Insufficient permissions to rename {doctype} '{name}'",
                "doctype": doctype,
                "name": name,
                "permission_error": True,
            }
        except Exception as e:
            frappe.db.rollback()
            log_failure("Document Rename Error", e)
            return {
                "success": False,
                "error": str(e) or f"Could not rename {doctype} '{name}'",
                "doctype": doctype,
                "name": name,
            }


# Make sure class name matches file name for discovery
document_rename = DocumentRename
