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
Aggregate Documents Tool for the Core Plugin.
Count/sum/avg/min/max with optional group-by through the permission-aware list API.
"""

from typing import Any, Dict, List

import frappe
from frappe import _

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core.field_guard import restricted_fields_for_doctype
from pibiassistant.plugins.core.tools.list_documents import apply_default_docstatus
from pibiassistant.plugins.limits import clamp_limit
from pibiassistant.plugins.query_errors import client_error_message, permission_error_result

FUNCTIONS = ("count", "sum", "avg", "min", "max")
NUMERIC_FIELDTYPES = {"Int", "Float", "Currency", "Percent", "Long Int"}
GROUPABLE_EXCLUDED = {"Text", "Long Text", "Small Text", "Text Editor", "Markdown Editor", "HTML Editor", "Code", "JSON", "Password", "Attach", "Attach Image"}
MAX_GROUPS = 500
DATE_FIELDTYPES = {"Date", "Datetime"}
PERIODS = ("day", "month", "quarter", "year")
# Frappe's group by validator rejects operators, so the expression is selected under
# an alias and grouped by that. Periods are numeric keys (YYYYMM, YYYYQ) that
# period_label turns into readable labels.
PERIOD_ALIAS = "pa_period"
PERIOD_SQL = {
    "day": "DATE(`{f}`)",
    "month": "YEAR(`{f}`) * 100 + MONTH(`{f}`)",
    "quarter": "YEAR(`{f}`) * 10 + QUARTER(`{f}`)",
    "year": "YEAR(`{f}`)",
}


def period_label(period: str, key: Any) -> Any:
    """Readable label for a numeric period key: 202503 -> 2025-03, 20253 -> 2025-Q3."""
    if key is None:
        return None
    if period == "month":
        return f"{int(key) // 100}-{int(key) % 100:02d}"
    if period == "quarter":
        return f"{int(key) // 10}-Q{int(key) % 10}"
    if period == "day":
        return str(key)
    return int(key)
STANDARD_DATES = {"creation", "modified"}
STANDARD_NUMERIC = {"idx": "Int", "docstatus": "Int"}


class AggregateDocuments(BaseTool):
    """Count, sum, average, min or max over documents, optionally grouped by one field."""

    def __init__(self):
        super().__init__()
        self.name = "aggregate_documents"
        self.description = (
            "Compute totals without fetching rows: count, sum, avg, min or max of fields, optionally "
            "grouped by one field (e.g. count ToDo by status, sum Sales Invoice grand_total by customer, "
            "outstanding_amount by company). Prefer this over list_documents for any totals, counts or "
            "rankings. Honours the user's permissions. Submittable doctypes default to submitted "
            "documents; pass a docstatus filter to change that. Worked examples: amounts owed to suppliers = "
            "doctype 'Purchase Invoice', aggregates sum outstanding_amount, group_by supplier (filters "
            "outstanding_amount > 0); an account balance = doctype 'GL Entry', sum debit and sum credit "
            "filtered by account (and is_cancelled=0), balance = debit - credit; stock value = doctype 'Bin', "
            "sum stock_value, group_by warehouse or item_code. For formal statements (Balance Sheet, "
            "Accounts Payable, Stock Balance) use report_list then generate_report."
        )
        self.requires_permission = None

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "DocType name, e.g. 'Sales Invoice'"},
                "aggregates": {
                    "type": "array",
                    "description": "What to compute. Default: a single count of documents.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "function": {"type": "string", "enum": list(FUNCTIONS)},
                            "field": {
                                "type": "string",
                                "description": "Field to aggregate; numeric for sum/avg. Omit for count.",
                            },
                        },
                        "required": ["function"],
                    },
                },
                "group_by": {"type": "string", "description": "Optional field to group by, e.g. 'status', 'customer'."},
                "period": {
                    "type": "string",
                    "enum": list(PERIODS),
                    "description": "Only with a Date/Datetime group_by: bucket it by day, month (YYYY-MM), quarter (YYYY-Qn) or year, returned in a 'period' column in chronological order. Example: sales per month = doctype 'Sales Invoice', group_by 'posting_date', period 'month', aggregates sum grand_total.",
                },
                "filters": {"type": "object", "description": "Frappe filters, same format as list_documents."},
                "order_by": {
                    "type": "string",
                    "description": "Result column then asc/desc, e.g. 'sum_grand_total desc'. Columns are named <function>_<field>, or 'count'.",
                },
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "maximum": MAX_GROUPS,
                    "description": "Maximum number of groups returned.",
                },
            },
            "required": ["doctype"],
        }

    @staticmethod
    def _row(row: Dict[str, Any], period: Any) -> Dict[str, Any]:
        row = dict(row)
        if period:
            row["period"] = period_label(period, row.pop(PERIOD_ALIAS, None))
        return row

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        filters = arguments.get("filters") or {}
        group_by = arguments.get("group_by") or None
        period = arguments.get("period") or None
        limit = clamp_limit(arguments.get("limit"), 50, MAX_GROUPS)

        if not doctype or not frappe.db.exists("DocType", doctype):
            return {"success": False, "error": f"DocType '{doctype}' not found"}

        from pibiassistant.core.security_config import ADMIN_ONLY_FIELDS, validate_document_access

        validation = validate_document_access(
            user=frappe.session.user, doctype=doctype, name=None, perm_type="read"
        )
        if not validation["success"]:
            return validation
        user_role = validation["role"]

        meta = frappe.get_meta(doctype)
        if meta.istable or meta.issingle:
            return {"success": False, "error": f"{doctype} is a child table or single doctype and cannot be aggregated."}

        from frappe.model import get_permitted_fields

        allowed = set(get_permitted_fields(doctype, ignore_virtual=True)) & set(meta.get_valid_columns())
        if user_role == "PA User" and ADMIN_ONLY_FIELDS.get(doctype) == "*":
            return {"success": False, "error": f"Insufficient read permissions for {doctype}"}
        blocked = restricted_fields_for_doctype(doctype, user_role)
        allowed -= blocked

        selects: List[str] = []
        columns: List[str] = []
        specs = arguments.get("aggregates") or [{"function": "count"}]
        if not isinstance(specs, list) or not all(isinstance(s, dict) for s in specs):
            return {"success": False, "error": "aggregates must be a list of {function, field} objects"}

        for spec in specs:
            function = str(spec.get("function", "")).lower()
            field = spec.get("field")
            if function not in FUNCTIONS:
                return {"success": False, "error": f"Unknown function '{function}'. Use: {', '.join(FUNCTIONS)}"}
            if function == "count":
                alias = "count" if not field else f"count_{field}"
                if field and field not in allowed:
                    return {"success": False, "error": f"Field '{field}' is not available in {doctype}"}
                selects.append(f"count(`{field or 'name'}`) as `{alias}`")
            else:
                if not field or field not in allowed:
                    return {"success": False, "error": f"Field '{field}' is not available in {doctype}"}
                field_meta = meta.get_field(field)
                fieldtype = field_meta.fieldtype if field_meta else STANDARD_NUMERIC.get(field)
                if function in ("sum", "avg") and fieldtype not in NUMERIC_FIELDTYPES:
                    return {"success": False, "error": f"'{field}' is {fieldtype}; {function} needs a numeric field"}
                alias = f"{function}_{field}"
                selects.append(f"{function}(`{field}`) as `{alias}`")
            if alias in columns:
                return {"success": False, "error": f"Duplicate aggregate {alias}"}
            columns.append(alias)

        if group_by:
            group_field = meta.get_field(group_by)
            if group_by not in allowed or (group_field and group_field.fieldtype in GROUPABLE_EXCLUDED):
                return {"success": False, "error": f"Cannot group {doctype} by '{group_by}'"}
            group_expr = f"`{group_by}`"
            group_column = group_by
            if period:
                field_type = group_field.fieldtype if group_field else ("Datetime" if group_by in STANDARD_DATES else None)
                if period not in PERIODS:
                    return {"success": False, "error": _("period must be one of: {0}").format(", ".join(PERIODS))}
                if field_type not in DATE_FIELDTYPES:
                    return {"success": False, "error": _("period needs a Date or Datetime group_by; '{0}' is not one.").format(group_by)}
                selects.insert(0, f"{PERIOD_SQL[period].format(f=group_by)} as `{PERIOD_ALIAS}`")
                group_expr = f"`{PERIOD_ALIAS}`"
                group_column = "period"
            else:
                selects.insert(0, group_expr)
        elif period:
            return {"success": False, "error": _("period requires group_by set to a Date or Datetime field.")}

        order_by = None
        orderable = columns + ([group_column] if group_by else [])
        if arguments.get("order_by"):
            parts = str(arguments["order_by"]).replace("`", "").split()
            direction = parts[1].lower() if len(parts) > 1 else "asc"
            if len(parts) > 2 or parts[0] not in orderable or direction not in ("asc", "desc"):
                return {
                    "success": False,
                    "error": f"order_by must be one of {', '.join(orderable)} followed by asc or desc",
                }
            order_by = f"`{PERIOD_ALIAS if parts[0] == 'period' and period else parts[0]}` {direction}"
        elif period:
            order_by = f"`{PERIOD_ALIAS}` asc"
        elif group_by:
            order_by = f"`{columns[0]}` desc"

        if doctype == "User" and user_role in ["PA User", "Default"]:
            filters = {**filters, "name": frappe.session.user} if isinstance(filters, dict) else filters
        filters, docstatus_defaulted = apply_default_docstatus(doctype, filters)

        try:
            rows = frappe.get_list(
                doctype,
                filters=filters,
                fields=selects,
                group_by=group_expr if group_by else None,
                order_by=order_by or "KEEP_DEFAULT_ORDERING",
                limit=limit,
                ignore_permissions=False,
            )
        except frappe.PermissionError as e:
            return permission_error_result(e, _("Insufficient read permissions for {0}").format(doctype))
        except Exception as e:
            friendly = client_error_message(e)
            return {"success": False, "error": friendly or str(e)[:2000] or type(e).__name__, "doctype": doctype}

        result = {
            "success": True,
            "doctype": doctype,
            "group_by": group_by,
            "period": period,
            "columns": ([group_column] if group_by else []) + columns,
            "data": [self._row(r, period) for r in rows],
            "count": len(rows),
            "has_more": bool(group_by) and len(rows) >= limit,
            "filters_applied": filters,
        }
        if docstatus_defaulted:
            result["message"] = "Submitted documents only (docstatus=1 by default); pass a docstatus filter to include others."
        return result


aggregate_documents = AggregateDocuments
