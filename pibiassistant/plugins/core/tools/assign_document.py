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

"""Assign a document to users, or remove an assignment."""

import json
from typing import Any, Dict, List, Optional

import frappe

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core.doc_actions import access_error, fail
from pibiassistant.plugins.query_errors import log_failure

MAX_ASSIGNEES = 10


def _users(value) -> List[str]:
    if isinstance(value, str):
        value = [v.strip() for v in value.split(",")] if not value.strip().startswith("[") else json.loads(value)
    return [u for u in (value or []) if isinstance(u, str) and u.strip()]


def check_assign(doctype: str, name: str, assign_to, action: str) -> Optional[str]:
    users = _users(assign_to)
    if not doctype or not name or not users:
        return "doctype, name and assign_to (one or more user emails) are required"
    if len(users) > MAX_ASSIGNEES:
        return f"At most {MAX_ASSIGNEES} users per call."
    if action not in ("add", "remove"):
        return "action must be 'add' or 'remove'"
    if not frappe.db.exists("DocType", doctype) or not frappe.db.exists(doctype, name):
        return f"{doctype} '{name}' not found"
    for user in users:
        if not frappe.db.exists("User", user):
            return f"User '{user}' not found. Use the exact email of an existing user."
        if action == "add":
            if not frappe.db.get_value("User", user, "enabled"):
                return f"User '{user}' is disabled."
            if not frappe.has_permission(doctype, "read", doc=name, user=user):
                return f"User '{user}' cannot read {doctype} '{name}', so it cannot be assigned to them."
    return None


def preview(arguments: Dict[str, Any]) -> str:
    doctype, name, action = arguments.get("doctype"), arguments.get("name"), arguments.get("action") or "add"
    problem = check_assign(doctype, name, arguments.get("assign_to"), action)
    if problem:
        return f"{doctype} '{name}'. Will be refused: {problem}"
    verb = "Assign" if action == "add" else "Remove the assignment of"
    return f"{verb} {doctype} '{name}' {'to' if action == 'add' else 'from'} {', '.join(_users(arguments.get('assign_to')))}."


class DocumentAssign(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "assign_document"
        self.description = (
            "Assign a document to one or more users (creates the native assignment and its ToDo, visible in the "
            "document's sidebar) or remove an assignment. Use the exact email of existing, enabled users who can "
            "read the document. Optional description and due date (YYYY-MM-DD). Needs the user's approval."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "DocType of the document"},
                "name": {"type": "string", "description": "Name/ID of the document"},
                "assign_to": {"type": "array", "items": {"type": "string"}, "description": "User emails (max 10)"},
                "action": {"type": "string", "enum": ["add", "remove"], "default": "add"},
                "description": {"type": "string", "description": "What the assignee should do (optional, add only)"},
                "date": {"type": "string", "description": "Due date YYYY-MM-DD (optional, add only)"},
            },
            "required": ["doctype", "name", "assign_to"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype, name = arguments.get("doctype"), arguments.get("name")
        action = arguments.get("action") or "add"
        users = _users(arguments.get("assign_to"))
        problem = check_assign(doctype, name, users, action)
        if problem:
            return fail(problem, doctype=doctype, name=name)
        blocked = access_error(doctype, name, "write")
        if blocked:
            return blocked
        try:
            from frappe.desk.form import assign_to

            if not frappe.has_permission(doctype, "read", doc=name):
                return fail(f"Insufficient permissions on {doctype} '{name}'", permission_error=True)
            if action == "add":
                payload = {"doctype": doctype, "name": name, "assign_to": users, "notify": 0}
                if arguments.get("description"):
                    payload["description"] = str(arguments["description"])[:1000]
                if arguments.get("date"):
                    payload["date"] = str(arguments["date"])[:10]
                assign_to.add(payload)
            else:
                for user in users:
                    assign_to.remove(doctype, name, user)
            frappe.db.commit()
            current = [row.allocated_to for row in frappe.get_all("ToDo", filters={"reference_type": doctype, "reference_name": name, "status": "Open"}, fields=["allocated_to"])]
            return {"success": True, "doctype": doctype, "name": name, "action": action, "assigned_now": current,
                    "message": f"{'Assigned' if action == 'add' else 'Removed assignment of'} {', '.join(users)}"}
        except frappe.PermissionError:
            return fail(f"Insufficient permissions on {doctype} '{name}'", permission_error=True)
        except Exception as e:
            frappe.db.rollback()
            log_failure("Document Assign Error", e)
            return fail(str(e) or f"Could not change the assignment of {doctype} '{name}'", doctype=doctype, name=name)


document_assign = DocumentAssign
