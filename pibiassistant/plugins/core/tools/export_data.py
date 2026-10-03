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

"""Export a list of documents to a CSV or Excel file, as a private downloadable file."""

import csv
import io
import re
from typing import Any, Dict, List

import frappe
from frappe.utils import now_datetime

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core.doc_actions import access_error, fail, save_private_file
from pibiassistant.plugins.core.tools.list_documents import apply_default_docstatus, normalize_filter_shapes
from pibiassistant.plugins.query_errors import log_failure

DEFAULT_LIMIT = 1000
MAX_LIMIT = 20000
SKIP_FIELDTYPES = frozenset({"Table", "Table MultiSelect", "HTML", "Section Break", "Column Break", "Tab Break", "Button", "Image", "Attach", "Attach Image", "Password", "Signature", "Heading", "Fold"})
# Credentials and sessions are never exported, whatever the caller's role.
NEVER_EXPORT = frozenset({"OAuth Bearer Token", "OAuth Client", "OAuth Authorization Code", "Email Account", "Social Login Key", "Connected App", "Token Cache"})


def default_fields(doctype: str) -> List[str]:
    meta = frappe.get_meta(doctype)
    fields = ["name"] + [f.fieldname for f in meta.fields if f.in_list_view and f.fieldtype not in SKIP_FIELDTYPES]
    if meta.is_submittable and "docstatus" not in fields:
        fields.append("docstatus")
    return list(dict.fromkeys(fields))[:30]


def check_export(doctype: str, fields) -> Any:
    """(error or None, usable fields)."""
    if not doctype or not frappe.db.exists("DocType", doctype):
        return f"DocType '{doctype}' not found", []
    meta = frappe.get_meta(doctype)
    if meta.issingle:
        return f"{doctype} is a single DocType: use get_document.", []
    if doctype in NEVER_EXPORT:
        return f"{doctype} cannot be exported through the assistant.", []
    from pibiassistant.core.security_config import SENSITIVE_FIELDS

    secret = set(SENSITIVE_FIELDS.get("all_doctypes", [])) | set(SENSITIVE_FIELDS.get(doctype, [])) | {f.fieldname for f in meta.fields if f.fieldtype == "Password"}
    if not fields:
        return None, [f for f in default_fields(doctype) if f not in secret]
    if not isinstance(fields, list) or len(fields) > 60:
        return "fields must be a list of at most 60 field names", []
    valid = set(meta.get_valid_columns())
    unknown = [f for f in fields if f not in valid]
    if unknown:
        return f"Unknown fields for {doctype}: {', '.join(unknown)}. Use get_doctype_info for valid fieldnames.", []
    blocked = [f for f in fields if f in secret]
    if blocked:
        return f"These fields cannot be exported: {', '.join(blocked)}.", []
    return None, list(fields)


def _limit(value) -> int:
    try:
        return max(1, min(int(value or DEFAULT_LIMIT), MAX_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT


def _cell(value):
    if value is None:
        return ""
    text = value if isinstance(value, (int, float)) else str(value)
    # A spreadsheet runs a leading = + - @ as a formula: keep text from becoming one.
    if isinstance(text, str) and text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


class DataExport(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "export_data"
        self.description = (
            "Export a list of documents to a CSV or Excel (xlsx) file and return a download link: customers, "
            "invoices of a period, items with stock... Same filters as list_documents (dates as "
            "['between', ['2026-01-01','2026-12-31']]); submittable DocTypes default to submitted documents. Pick "
            "the columns with fields (default: the list-view columns). Up to 20,000 rows; secret fields are never "
            "exported. Use this for files; to answer a question in chat use list_documents or aggregate_documents. "
            "Copy the returned download_link verbatim. Needs the user's approval."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "DocType to export (e.g. 'Customer')"},
                "fields": {"type": "array", "items": {"type": "string"}, "description": "Field names (optional)"},
                "filters": {"type": "object", "description": "Frappe filters, same format as list_documents"},
                "order_by": {"type": "string", "description": "e.g. 'creation desc' (optional)"},
                "format": {"type": "string", "enum": ["xlsx", "csv"], "default": "xlsx"},
                "limit": {"type": "integer", "default": DEFAULT_LIMIT, "description": f"Max rows, up to {MAX_LIMIT}"},
            },
            "required": ["doctype"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        fmt = str(arguments.get("format") or "xlsx").lower()
        if fmt not in ("xlsx", "csv"):
            return fail("format must be 'xlsx' or 'csv'", doctype=doctype)
        problem, fields = check_export(doctype, arguments.get("fields"))
        if problem:
            return fail(problem, doctype=doctype)
        blocked = access_error(doctype, "", "read")
        if blocked:
            return blocked
        limit = _limit(arguments.get("limit"))
        order_by = str(arguments.get("order_by") or "").strip()
        if order_by and not re.fullmatch(r"[\w` ]+(\.[\w`]+)?( (asc|desc))?(, ?[\w` ]+( (asc|desc))?)*", order_by, re.I):
            return fail("order_by must look like 'creation desc'", doctype=doctype)
        try:
            if not frappe.has_permission(doctype, "export") and not frappe.has_permission(doctype, "read"):
                return fail(f"You do not have permission to read {doctype}.", doctype=doctype, permission_error=True)
            filters = normalize_filter_shapes(doctype, arguments.get("filters") or {})
            filters, defaulted = apply_default_docstatus(doctype, filters)
            rows = frappe.get_list(doctype, filters=filters, fields=fields, order_by=order_by or None, limit_page_length=limit + 1)
            truncated = len(rows) > limit
            rows = rows[:limit]
            table = [fields] + [[_cell(row.get(f)) for f in fields] for row in rows]
            stamp = now_datetime().strftime("%Y%m%d-%H%M%S")
            filename = f"export-{re.sub(r'[^A-Za-z0-9]+', '_', doctype)}-{stamp}.{fmt}"
            if fmt == "csv":
                buffer = io.StringIO()
                csv.writer(buffer).writerows(table)
                content = ("﻿" + buffer.getvalue()).encode("utf-8")
            else:
                from frappe.utils.xlsxutils import make_xlsx

                content = make_xlsx(table, doctype[:31]).getvalue()
            saved = save_private_file(filename, content)
            frappe.db.commit()
            return {
                "success": True, "doctype": doctype, "format": fmt, "rows": len(rows), "columns": fields,
                "truncated": truncated, "filters_applied": filters, **saved,
                "message": f"{len(rows)} row(s) exported{' (limit reached, narrow the filters for the rest)' if truncated else ''}. "
                          f"Copy this markdown link VERBATIM into your answer: {saved['download_link']}",
            }
        except frappe.PermissionError:
            return fail(f"You do not have permission to read {doctype}.", doctype=doctype, permission_error=True)
        except Exception as e:
            frappe.db.rollback()
            log_failure("Data Export Error", e)
            return fail(str(e) or f"Could not export {doctype}", doctype=doctype)


def preview(arguments: Dict[str, Any]) -> str:
    doctype = arguments.get("doctype")
    problem, fields = check_export(doctype, arguments.get("fields"))
    if problem:
        return f"Export {doctype}. Will be refused: {problem}"
    return (
        f"Export {doctype} to {str(arguments.get('format') or 'xlsx').lower()}: {len(fields)} column(s), "
        f"up to {_limit(arguments.get('limit'))} rows. The file is private to you."
    )


data_export = DataExport
