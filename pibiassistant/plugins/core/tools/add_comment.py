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

"""Add a comment to a document's timeline."""

from typing import Any, Dict, Optional

import frappe

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core.doc_actions import access_error, fail
from pibiassistant.plugins.query_errors import log_failure

MAX_COMMENT_CHARS = 5000


def check_comment(doctype: str, name: str, comment) -> Optional[str]:
    if not doctype or not name or not isinstance(comment, str) or not comment.strip():
        return "doctype, name and comment are required"
    if len(comment) > MAX_COMMENT_CHARS:
        return f"The comment is longer than {MAX_COMMENT_CHARS} characters."
    if not frappe.db.exists("DocType", doctype) or not frappe.db.exists(doctype, name):
        return f"{doctype} '{name}' not found"
    return None


def preview(arguments: Dict[str, Any]) -> str:
    doctype, name, comment = arguments.get("doctype"), arguments.get("name"), arguments.get("comment")
    problem = check_comment(doctype, name, comment)
    if problem:
        return f"{doctype} '{name}'. Will be refused: {problem}"
    shown = comment.strip().replace("\n", " ")
    return f"Add a comment to {doctype} '{name}': \"{shown[:160]}{'...' if len(shown) > 160 else ''}\""


class DocumentComment(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "add_comment"
        self.description = (
            "Add a comment to a document's timeline (like writing in the comment box of the form), e.g. to leave a "
            "note about a decision or a follow-up. It is shown under the user's name and visible to everyone who "
            "can read the document. Plain text, up to 5000 characters. Needs the user's approval."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "DocType of the document"},
                "name": {"type": "string", "description": "Name/ID of the document"},
                "comment": {"type": "string", "description": "The comment text (plain text)"},
            },
            "required": ["doctype", "name", "comment"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype, name, comment = arguments.get("doctype"), arguments.get("name"), arguments.get("comment")
        problem = check_comment(doctype, name, comment)
        if problem:
            return fail(problem, doctype=doctype, name=name)
        blocked = access_error(doctype, name, "write")
        if blocked:
            return blocked
        try:
            from frappe.desk.form.utils import add_comment

            content = frappe.utils.escape_html(comment.strip()).replace("\n", "<br>")
            added = add_comment(
                reference_doctype=doctype, reference_name=name, content=content,
                comment_email=frappe.session.user, comment_by=frappe.utils.get_fullname(frappe.session.user),
            )
            frappe.db.commit()
            return {"success": True, "doctype": doctype, "name": name, "comment_id": getattr(added, "name", None),
                    "message": f"Comment added to {doctype} '{name}'"}
        except frappe.PermissionError:
            return fail(f"Insufficient permissions on {doctype} '{name}'", permission_error=True)
        except Exception as e:
            frappe.db.rollback()
            log_failure("Document Comment Error", e)
            return fail(str(e) or f"Could not comment on {doctype} '{name}'", doctype=doctype, name=name)


document_comment = DocumentComment
