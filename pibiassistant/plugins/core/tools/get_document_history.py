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
Document History Tool for the Core Plugin.
Who changed what on a document (Version log), plus optional comments, assignments and attachments.
"""

import json
import re
from typing import Any, Dict, List, Optional

import frappe
from frappe import _
from frappe.utils import strip_html

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core import doc_actions
from pibiassistant.plugins.core.field_guard import restricted_fields_for_doctype
from pibiassistant.plugins.limits import clamp_limit
from pibiassistant.plugins.query_errors import log_failure

MAX_LIMIT = 50
MAX_CHANGES = 40
VALUE_CHARS = 200
SECTIONS = ("versions", "comments", "assignments", "attachments")
MASK = "***"
CREDENTIAL_NAME = re.compile(r"pass(word|wd)|secret|token|api_?key|private_?key|credential|iban|bank_account", re.I)


def _clip(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    return text if len(text) <= VALUE_CHARS else text[: VALUE_CHARS - 1] + "…"


class _FieldRules:
    """Per-doctype visibility for one document: hidden (drop), masked (show ***)."""

    def __init__(self, doc, blocked: set):
        self.doc = doc
        self.blocked = blocked
        self._cache: Dict[Any, Optional[Any]] = {}

    def _df(self, doctype: str, fieldname: str):
        return frappe.get_meta(doctype).get_field(fieldname)

    def hidden(self, doctype: str, fieldname: str, parent_df=None) -> bool:
        key = (doctype, fieldname)
        if key not in self._cache:
            df = self._df(doctype, fieldname)
            hide = False
            if df is None:
                # Standard columns (owner, modified...) stay visible; unknown keys are stale fields.
                hide = fieldname not in ("owner", "creation", "modified", "modified_by", "docstatus", "idx")
            elif df.fieldtype in ("Section Break", "Column Break", "Tab Break", "HTML", "Button"):
                hide = True
            elif df.permlevel:
                try:
                    hide = not self.doc.has_permlevel_access_to(fieldname, df, "read")
                except Exception:
                    hide = True
            self._cache[key] = hide
        return self._cache[key]

    def masked(self, doctype: str, fieldname: str) -> bool:
        df = self._df(doctype, fieldname)
        return bool(
            fieldname in self.blocked
            or CREDENTIAL_NAME.search(fieldname)
            or (df is not None and df.fieldtype == "Password")
        )

    def label(self, doctype: str, fieldname: str) -> str:
        df = self._df(doctype, fieldname)
        return (df.label if df is not None and df.label else None) or fieldname.replace("_", " ").title()

    def change(self, doctype: str, fieldname: str, old: Any, new: Any, prefix: str = "") -> Optional[Dict[str, Any]]:
        if self.hidden(doctype, fieldname):
            return None
        hide = self.masked(doctype, fieldname)
        label = self.label(doctype, fieldname)
        return {
            "field": f"{prefix}{fieldname}",
            "label": f"{prefix}{label}" if prefix else label,
            "old": MASK if hide and old not in (None, "") else _clip(old),
            "new": MASK if hide and new not in (None, "") else _clip(new),
        }


def _parse_version(data: Any, doctype: str, rules: _FieldRules) -> Dict[str, Any]:
    try:
        payload = json.loads(data) if isinstance(data, str) else (data or {})
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    changed: List[Dict[str, Any]] = []
    for item in payload.get("changed") or []:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            entry = rules.change(doctype, str(item[0]), item[1], item[2])
            if entry:
                changed.append(entry)

    for item in payload.get("row_changed") or []:
        if not (isinstance(item, (list, tuple)) and len(item) >= 4 and isinstance(item[3], (list, tuple))):
            continue
        table, idx = str(item[0]), item[1]
        if rules.hidden(doctype, table):
            continue
        df = frappe.get_meta(doctype).get_field(table)
        child_doctype = df.options if df is not None else None
        if not child_doctype:
            continue
        for sub in item[3]:
            if isinstance(sub, (list, tuple)) and len(sub) >= 3:
                entry = rules.change(child_doctype, str(sub[0]), sub[1], sub[2], prefix=f"{table}[{idx}].")
                if entry:
                    changed.append(entry)

    def count(key: str) -> int:
        total = 0
        for item in payload.get(key) or []:
            if isinstance(item, (list, tuple)) and item and not rules.hidden(doctype, str(item[0])):
                total += 1
        return total

    return {
        "changed": changed[:MAX_CHANGES],
        "rows_added": count("added"),
        "rows_removed": count("removed"),
    }


class GetDocumentHistory(BaseTool):
    """Read the change history of one document the caller is allowed to read."""

    def __init__(self):
        super().__init__()
        self.name = "get_document_history"
        self.description = (
            "History of a document: who changed what and when (field, old value, new value), newest first. "
            "Optionally also its comments, assignments and attachments. Use it for 'who changed this "
            "invoice', 'what was the previous value' or 'show the audit trail'. Only fields the user may "
            "read are shown; passwords and credentials are masked."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "DocType name, e.g. 'Sales Invoice'"},
                "name": {"type": "string", "description": "Document name"},
                "include": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(SECTIONS)},
                    "default": ["versions", "comments"],
                    "description": "Sections to return. Default versions and comments.",
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "maximum": MAX_LIMIT,
                    "description": "Maximum entries per section. Default 20, maximum 50.",
                },
            },
            "required": ["doctype", "name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        name = arguments.get("name")
        limit = clamp_limit(arguments.get("limit"), 20, MAX_LIMIT)
        include = arguments.get("include")
        if include is None:
            include = ["versions", "comments"]
        if not isinstance(include, list) or not include or any(s not in SECTIONS for s in include):
            return doc_actions.fail(_("include must be a list of: {0}").format(", ".join(SECTIONS)))
        if not doctype or not name or not isinstance(doctype, str) or not isinstance(name, str):
            return doc_actions.fail(_("doctype and name are required"))

        # The read check always comes first: nothing below runs for a document the caller cannot read.
        denied = doc_actions.access_error(doctype, name, "read")
        if denied:
            return denied
        try:
            doc = frappe.get_doc(doctype, name)
            doc.check_permission("read")
        except frappe.DoesNotExistError:
            return doc_actions.fail(_("{0} {1} not found").format(doctype, name))
        except frappe.PermissionError:
            return doc_actions.fail(_("Insufficient read permissions for {0} {1}").format(doctype, name))

        from pibiassistant.core.security_config import get_user_primary_role

        role = get_user_primary_role(frappe.session.user)
        rules = _FieldRules(doc, restricted_fields_for_doctype(doctype, role))
        result: Dict[str, Any] = {"success": True, "doctype": doctype, "name": name}
        try:
            if "versions" in include:
                rows = frappe.get_all(
                    "Version",
                    filters={"ref_doctype": doctype, "docname": name},
                    fields=["creation", "owner", "data"],
                    order_by="creation desc",
                    limit_page_length=limit,
                )
                versions = []
                for row in rows:
                    entry = _parse_version(row.data, doctype, rules)
                    if entry["changed"] or entry["rows_added"] or entry["rows_removed"]:
                        versions.append({"date": str(row.creation), "user": row.owner, **entry})
                result["versions"] = versions
            if "comments" in include:
                rows = frappe.get_all(
                    "Comment",
                    filters={"reference_doctype": doctype, "reference_name": name, "comment_type": "Comment"},
                    fields=["creation", "comment_email", "content"],
                    order_by="creation desc",
                    limit_page_length=limit,
                )
                result["comments"] = [
                    {"date": str(r.creation), "user": r.comment_email, "text": _clip(strip_html(r.content or "").strip())}
                    for r in rows
                ]
            if "assignments" in include:
                rows = frappe.get_all(
                    "ToDo",
                    filters={"reference_type": doctype, "reference_name": name},
                    fields=["creation", "allocated_to", "status", "owner", "date"],
                    order_by="creation desc",
                    limit_page_length=limit,
                )
                result["assignments"] = [
                    {
                        "date": str(r.creation),
                        "assigned_to": r.allocated_to,
                        "assigned_by": r.owner,
                        "status": r.status,
                        "due": str(r.date) if r.date else None,
                    }
                    for r in rows
                ]
            if "attachments" in include:
                rows = frappe.get_all(
                    "File",
                    filters={"attached_to_doctype": doctype, "attached_to_name": name},
                    fields=["creation", "file_name", "file_url", "is_private"],
                    order_by="creation desc",
                    limit_page_length=limit,
                )
                result["attachments"] = [
                    {"date": str(r.creation), "file_name": r.file_name, "url": r.file_url, "private": bool(r.is_private)}
                    for r in rows
                ]
        except Exception as e:
            log_failure("Document History Error", e)
            return doc_actions.fail(_("Could not read the history of {0} {1}").format(doctype, name))

        result["limit"] = limit
        return result


get_document_history = GetDocumentHistory
