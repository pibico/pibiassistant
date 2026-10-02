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
Document Listing Tool for Core Plugin.
Lists and searches Frappe documents with filtering capabilities.
"""

from typing import Any, Dict, List, Optional

import frappe
from frappe import _

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core.field_guard import restricted_fields_for_doctype
from pibiassistant.plugins.limits import clamp_int, clamp_limit
from pibiassistant.plugins.row_permissions import drop_unreadable_rows, has_row_permission_hook
from pibiassistant.plugins.query_errors import client_error_message, log_failure, single_doctype_message

# Operators Frappe accepts as the first element of a list-style filter value.
# Anything else in that position means the list is a set of values, not [op, value].
FILTER_OPERATORS = {
    "=",
    "!=",
    ">",
    "<",
    ">=",
    "<=",
    "like",
    "not like",
    "in",
    "not in",
    "is",
    "between",
    "descendants of",
    "not descendants of",
    "ancestors of",
    "not ancestors of",
}


def is_submittable(doctype: str) -> bool:
    """Whether the DocType carries docstatus semantics (draft/submitted/cancelled)."""
    try:
        return bool(frappe.get_meta(doctype).is_submittable)
    except Exception:
        # Missing or virtual DocTypes are treated as non-submittable — the caller's
        # filters are then passed through untouched and Frappe reports the real error.
        return False


def filters_reference_docstatus(filters: Any) -> bool:
    """True when the caller already constrained docstatus, in any supported filter form."""
    if isinstance(filters, dict):
        return "docstatus" in filters

    if isinstance(filters, (list, tuple)):
        # A single unwrapped condition, e.g. ["docstatus", "=", 1]
        if filters and isinstance(filters[0], str):
            return "docstatus" in filters

        for condition in filters:
            if not isinstance(condition, (list, tuple)) or not condition:
                continue
            # ["doctype", "fieldname", op, value] or ["fieldname", op, value]
            fieldname = condition[1] if len(condition) >= 4 else condition[0]
            if fieldname == "docstatus":
                return True

    return False


def normalize_docstatus_filter(filters: Any) -> Any:
    """Accept a bare list of docstatus values, e.g. [0, 1], as an `in` filter.

    Frappe reads a list filter value as [operator, value], so an explicit
    {"docstatus": [0, 1]} would otherwise be parsed as the operator "0".
    """
    if not isinstance(filters, dict):
        return filters

    value = filters.get("docstatus")
    if not isinstance(value, (list, tuple)) or not value:
        return filters

    first = value[0]
    if isinstance(first, str) and first.lower() in FILTER_OPERATORS:
        return filters

    normalized = dict(filters)
    normalized["docstatus"] = ["in", list(value)]
    return normalized


def _date_range(value: str):
    """('2026-01-01', '2026-12-31') for '2026', ('2026-05-01', '2026-05-31') for '2026-05'; else None."""
    import calendar
    import re

    year = re.fullmatch(r"(\d{4})", value)
    if year:
        return f"{year.group(1)}-01-01", f"{year.group(1)}-12-31"
    month = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", value)
    if month:
        last = calendar.monthrange(int(month.group(1)), int(month.group(2)))[1]
        return f"{month.group(0)}-01", f"{month.group(0)}-{last:02d}"
    return None


def normalize_filter_shapes(doctype: str, filters: Any, fieldtype_of=None) -> Any:
    """Repair filter shapes models commonly send, which Frappe reads as "no match" instead of failing.

    ["between", a, b] -> ["between", [a, b]]; ["in", a, b] -> ["in", [a, b]];
    [field, "between", a, b] -> [field, "between", [a, b]]; "2026" or "2026-05" on a Date field
    -> the whole year or month.
    """
    if fieldtype_of is None:

        def fieldtype_of(fieldname):
            try:
                field = frappe.get_meta(doctype).get_field(fieldname)
                return field.fieldtype if field else None
            except Exception:
                return None

    def fix_value(fieldname, value):
        if isinstance(value, str) and fieldtype_of(fieldname) in ("Date", "Datetime"):
            span = _date_range(value.strip())
            if span:
                return ["between", list(span)]
        if isinstance(value, (list, tuple)) and len(value) == 3 and str(value[0]).lower() in ("between", "in", "not in"):
            op = str(value[0]).lower()
            if not isinstance(value[1], (list, tuple)):
                return [op, [value[1], value[2]]]
        if isinstance(value, (list, tuple)) and len(value) > 3 and str(value[0]).lower() in ("in", "not in"):
            if not isinstance(value[1], (list, tuple)):
                return [str(value[0]).lower(), list(value[1:])]
        return value

    if isinstance(filters, dict):
        return {key: fix_value(key, value) for key, value in filters.items()}

    if isinstance(filters, (list, tuple)):
        conditions = []
        for cond in filters:
            if isinstance(cond, (list, tuple)) and len(cond) == 4 and str(cond[1]).lower() in ("between", "in", "not in") and not isinstance(cond[2], (list, tuple)):
                cond = [cond[0], cond[1], [cond[2], cond[3]]]
            elif isinstance(cond, (list, tuple)) and len(cond) == 3 and cond[1] == "=" and isinstance(cond[2], str):
                fixed = fix_value(cond[0], cond[2])
                if fixed is not cond[2]:
                    cond = [cond[0], fixed[0], fixed[1]]
            conditions.append(cond)
        return conditions
    return filters


def apply_default_docstatus(doctype: str, filters: Any) -> tuple:
    """Default submittable DocTypes to submitted documents only.

    Without this, cancelled (docstatus=2) and draft (docstatus=0) documents are
    returned alongside submitted ones with their monetary fields intact, and any
    consumer aggregating the result set gets a silently wrong total.

    Returns (filters, applied) where `applied` says whether the default was added.
    """
    filters = normalize_filter_shapes(doctype, filters)
    if not is_submittable(doctype):
        return filters, False

    if filters_reference_docstatus(filters):
        return normalize_docstatus_filter(filters), False

    if isinstance(filters, dict):
        defaulted = dict(filters)
        defaulted["docstatus"] = 1
        return defaulted, True

    if isinstance(filters, (list, tuple)):
        # An unwrapped condition such as ["status", "=", "Paid"] has to be nested first.
        conditions = [list(filters)] if filters and isinstance(filters[0], str) else list(filters)
        return conditions + [["docstatus", "=", 1]], True

    return {"docstatus": 1}, True


# Ranked candidates offered per unmatched Link filter value.
MAX_LINK_SUGGESTIONS = 5


def equality_filter_pairs(filters: Any) -> List[tuple]:
    """(fieldname, value) pairs for filters compared to a single value by equality.

    Only these can be checked for existence — an operator like `like` or `in`
    already expresses that the caller does not know the exact value.
    """
    pairs = []

    if isinstance(filters, dict):
        for fieldname, value in filters.items():
            if isinstance(value, str):
                pairs.append((fieldname, value))
            elif isinstance(value, (list, tuple)) and len(value) == 2:
                operator, operand = value
                if isinstance(operator, str) and operator == "=" and isinstance(operand, str):
                    pairs.append((fieldname, operand))
        return pairs

    if isinstance(filters, (list, tuple)):
        conditions = [filters] if filters and isinstance(filters[0], str) else filters
        for condition in conditions:
            if not isinstance(condition, (list, tuple)) or len(condition) < 3:
                continue
            # ["doctype", "fieldname", op, value] or ["fieldname", op, value]
            fieldname, operator, value = condition[1:4] if len(condition) >= 4 else condition[0:3]
            if operator == "=" and isinstance(value, str):
                pairs.append((fieldname, value))

    return pairs


def link_filter_targets(doctype: str, filters: Any) -> Dict[str, tuple]:
    """Map fieldname -> (target DocType, value) for Link fields filtered by equality."""
    pairs = equality_filter_pairs(filters)
    if not pairs:
        return {}

    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return {}

    targets = {}
    for fieldname, value in pairs:
        if not value:
            continue
        field = meta.get_field(fieldname)
        if not field or field.fieldtype != "Link" or not field.options:
            continue
        targets[fieldname] = (field.options, value)

    return targets


def link_suggestions(target_doctype: str, value: str) -> List[str]:
    """Ranked candidate names for an unmatched Link value, via search_link resolution.

    Falls back to the first word of a multi-word value, since search_link matches
    on substrings and a typo late in the value would otherwise return nothing.
    """
    from .search_tools import SearchTools

    queries = [value]
    words = value.split()
    if words and words[0] != value:
        queries.append(words[0])

    for query in queries:
        response = SearchTools.search_link(doctype=target_doctype, query=query)
        if not response.get("success"):
            return []

        suggestions = [
            candidate.get("value") for candidate in response.get("results") or [] if candidate.get("value")
        ]
        if suggestions:
            return suggestions[:MAX_LINK_SUGGESTIONS]

    return []


def resolve_unmatched_link_filters(doctype: str, filters: Any) -> Dict[str, Dict[str, Any]]:
    """Explain a zero-row result caused by Link filter values that match no record.

    "No records" and "that entity does not exist" are indistinguishable to a
    consumer otherwise, so an approximate name passed straight into a filter reads
    as a legitimate business answer. Only called when the result set is empty.
    """
    unresolved = {}

    for fieldname, (target_doctype, value) in link_filter_targets(doctype, filters).items():
        try:
            if not frappe.db.exists("DocType", target_doctype):
                continue

            # Without read access on the target, neither existence nor candidates
            # are ours to report.
            if not frappe.has_permission(target_doctype, "read"):
                continue

            # The value resolves — zero rows is a real answer, not a bad filter.
            if frappe.db.exists(target_doctype, value):
                continue

            unresolved[fieldname] = {
                "value": value,
                "matched": False,
                "target_doctype": target_doctype,
                "suggestions": link_suggestions(target_doctype, value),
            }
        except Exception as e:
            # Diagnostics must never turn a successful query into a failure.
            frappe.log_error(
                title=_("Link Filter Resolution Error"),
                message=f"Error resolving {doctype}.{fieldname}: {str(e)}",
            )

    return unresolved


def child_table_parent(doctype: str, filters: Any):
    """Parent DocType named by a parenttype filter, which lets Frappe read all fields of a child table."""
    try:
        if not frappe.get_meta(doctype).istable:
            return None
    except Exception:
        return None
    if isinstance(filters, dict):
        value = filters.get("parenttype")
        if isinstance(value, (list, tuple)) and len(value) == 2 and value[0] == "=":
            value = value[1]
        if isinstance(value, str) and value:
            return value
    return None


def omitted_fields(requested: List[Any], rows: List[Any]) -> List[str]:
    """Plain requested fieldnames that a non-empty result does not carry."""
    if not rows or not isinstance(rows[0], dict):
        return []
    present = set(rows[0])
    return [
        field
        for field in requested
        if isinstance(field, str) and field.isidentifier() and field not in present
    ]


NUMERIC_FIELDTYPES = {"Check", "Int", "Float", "Currency", "Percent", "Long Int", "Rating"}


def filter_conditions(filters: Any) -> List[tuple]:
    """(fieldname, operator, value) triples from the dict and list filter forms."""
    triples = []
    if isinstance(filters, dict):
        for fieldname, value in filters.items():
            if isinstance(value, (list, tuple)) and value and isinstance(value[0], str) and value[0].lower() in FILTER_OPERATORS:
                triples.append((fieldname, value[0].lower(), value[1] if len(value) > 1 else None))
            else:
                triples.append((fieldname, "=", value))
    elif isinstance(filters, (list, tuple)):
        conditions = [filters] if filters and isinstance(filters[0], str) else filters
        for condition in conditions:
            if not isinstance(condition, (list, tuple)):
                continue
            if len(condition) >= 4:
                triples.append((condition[1], str(condition[2]).lower(), condition[3]))
            elif len(condition) == 3:
                triples.append((condition[0], str(condition[1]).lower(), condition[2]))
    return triples


def invalid_filter_message(doctype: str, filters: Any) -> Optional[str]:
    """Reason a filter would be silently coerced by the database instead of applied, or None."""
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return None
    for fieldname, operator, value in filter_conditions(filters):
        if operator == "between" and not (isinstance(value, (list, tuple)) and len(value) == 2):
            return _("Filter on '{0}': 'between' needs a list of exactly two values, e.g. ['between', ['2026-01-01', '2026-01-31']].").format(fieldname)
        if operator in ("in", "not in") and not isinstance(value, (list, tuple, str)):
            return _("Filter on '{0}': '{1}' needs a list of values.").format(fieldname, operator)
        field = meta.get_field(fieldname) if isinstance(fieldname, str) else None
        if field and field.fieldtype in NUMERIC_FIELDTYPES and operator in ("=", "!=", ">", "<", ">=", "<=") and value is not None:
            try:
                float(value)
            except (TypeError, ValueError):
                return _("Filter on '{0}': '{1}' is not a number; {2} fields take numeric values (Check fields take 0 or 1).").format(fieldname, value, field.fieldtype)
    return None


class DocumentList(BaseTool):
    """
    Tool for listing and searching Frappe documents.

    Provides capabilities for:
    - Searching documents with filters
    - Pagination support
    - Field selection
    - Permission checking
    """

    def __init__(self):
        super().__init__()
        self.name = "list_documents"
        self.description = "Search and list Frappe documents with optional filtering. Use this when users want to find records, get lists of documents, or search for data. This is the primary tool for data exploration and discovery. For submittable DocTypes (invoices, orders, entries) only submitted documents are returned unless you pass docstatus explicitly. If a query returns nothing because a Link filter value matches no record, the response carries unresolved_filters with ranked suggestions — check it before reporting that no data exists."
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The Frappe DocType to search (e.g., 'Customer', 'Sales Invoice', 'Item', 'User'). Must match exact DocType name.",
                },
                "filters": {
                    "type": "object",
                    "default": {},
                    "description": "Search filters as key-value pairs. Examples: {'status': 'Active'}, {'customer_type': 'Company'}, {'creation': ['>', '2024-01-01']}. Use empty {} to get all records. For submittable DocTypes, docstatus=1 (submitted) is applied automatically unless you set docstatus yourself — pass {'docstatus': 2} for cancelled, {'docstatus': [0, 1]} for drafts and submitted.",
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific fields to retrieve. Examples: ['name', 'customer_name', 'email'], ['name', 'item_name', 'item_code']. Leave empty to get standard fields.",
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "maximum": 1000,
                    "description": "Maximum number of records to return. Default is 20, maximum is 1000.",
                },
                "start": {
                    "type": "integer",
                    "default": 0,
                    "description": "Rows to skip, for paging. When the result has has_more=true, pass its next_start here to get the next page.",
                },
                "order_by": {
                    "type": "string",
                    "description": "Order results by field, e.g. 'creation desc', 'name asc'. Omit to use the DocType's own default ordering (usually modified desc).",
                },
            },
            "required": ["doctype"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List documents with filters"""
        doctype = arguments.get("doctype")
        filters = arguments.get("filters", {})
        fields = arguments.get("fields")
        if not isinstance(fields, list) or not fields:
            fields = ["name", "creation", "modified"]
        limit = clamp_limit(arguments.get("limit"), 20, 1000)
        start = clamp_int(arguments.get("start"), 0, 0, 1_000_000)
        # Use Frappe's sentinel so it applies its own intelligent default ordering.
        # Also guard against empty string from API clients.
        order_by = arguments.get("order_by") or "KEEP_DEFAULT_ORDERING"

        single_message = single_doctype_message(doctype)
        if single_message:
            return {"success": False, "error": single_message, "doctype": doctype}

        filters = normalize_filter_shapes(doctype, filters)
        invalid = invalid_filter_message(doctype, filters)
        if invalid:
            return {"success": False, "error": invalid, "doctype": doctype}

        current_user = frappe.session.user

        # Import security validation
        from pibiassistant.core.security_config import (
            filter_sensitive_fields,
            validate_document_access,
        )

        # Validate document access with comprehensive permission checking
        validation_result = validate_document_access(
            user=frappe.session.user,
            doctype=doctype,
            name=None,  # No specific document for list operation
            perm_type="read",
        )

        if not validation_result["success"]:
            return validation_result

        user_role = validation_result["role"]

        # SECURITY: Special handling for User DocType - non-admins can only see themselves
        if doctype == "User" and user_role in ["PA User", "Default"]:
            # Filter to only show current user
            if not filters:
                filters = {}
            filters["name"] = current_user

        # Submittable DocTypes default to submitted documents only, so cancelled and
        # draft records never reach a consumer that is summing monetary fields.
        filters, docstatus_defaulted = apply_default_docstatus(doctype, filters)

        requested_fields = list(fields)
        try:
            # Filter sensitive fields from requested fields for PA Users
            if user_role == "PA User":
                restricted_fields = restricted_fields_for_doctype(doctype, user_role)

                # Filter out restricted fields from requested fields
                filtered_fields = [field for field in fields if field not in restricted_fields]
                if not filtered_fields:
                    filtered_fields = ["name"]  # Always allow name field
                fields = filtered_fields

            query_fields = fields
            if has_row_permission_hook(doctype) and "name" not in fields and "*" not in fields:
                query_fields = ["name", *fields]

            # Get documents with Frappe's permission-aware list API.
            documents = frappe.get_list(
                doctype,
                filters=filters,
                fields=query_fields,
                limit=limit,
                start=start,
                order_by=order_by,
                ignore_permissions=False,  # Ensure permission checking
                parent_doctype=child_table_parent(doctype, filters),
            )

            fetched = len(documents)
            documents = drop_unreadable_rows(doctype, documents)
            hidden = fetched - len(documents)

            # Filter sensitive fields from document data
            filtered_documents = []
            for doc in documents:
                filtered_doc = filter_sensitive_fields(doc, doctype, user_role)
                filtered_documents.append(filtered_doc)

            # Get permission-aware total count for pagination info.
            # Use string aggregate only — dict form causes "Unknown column 'table.scalar'"
            # on MariaDB when filters include docstatus. See: PA PR fix.
            try:
                count_result = frappe.get_list(
                    doctype,
                    filters=filters,
                    fields=["count(name) as count"],
                    limit=1,
                    ignore_permissions=False,
                )
                total_count = count_result[0].get("count") if count_result else 0
            except Exception:
                frappe.log_error(
                    title=f"list_documents: count query failed for {doctype}",
                    message=frappe.get_traceback(),
                )
                total_count = None

            message = f"Found {len(filtered_documents)} {doctype} records"
            if docstatus_defaulted:
                message += (
                    " (submitted only — docstatus=1 applied by default; "
                    "pass docstatus explicitly to include drafts or cancelled documents)"
                )

            result = {
                "success": True,
                "doctype": doctype,
                "data": filtered_documents,
                "count": len(filtered_documents),
                "total_count": total_count - hidden if total_count is not None else None,
                "has_more": (total_count > start + fetched) if total_count is not None else fetched >= limit,
                "filters_applied": filters,
                "message": message,
            }

            if result["has_more"]:
                result["next_start"] = start + fetched

            omitted = omitted_fields(requested_fields, documents)
            if omitted:
                result["omitted_fields"] = omitted
                result["message"] += ". " + _(
                    "Some requested fields were not returned (unknown, restricted or not readable by this user): {0}."
                ).format(", ".join(omitted))
                if "parent" in omitted and child_table_parent(doctype, None) is None and frappe.get_meta(doctype).istable:
                    result["message"] += " " + _("For child tables, add a parenttype filter (e.g. {'parenttype': 'Sales Invoice'}) to read parent.")

            # A zero-row result may mean the filter value itself never existed.
            # Additive metadata only — the query still succeeded.
            if not filtered_documents:
                unresolved_filters = resolve_unmatched_link_filters(doctype, filters)
                if unresolved_filters:
                    result["unresolved_filters"] = unresolved_filters
                    result["message"] += (
                        f" — but these filter values match no record: "
                        f"{', '.join(sorted(unresolved_filters))}. This is an unresolved filter, "
                        "not an empty result. See unresolved_filters for candidates."
                    )

            # Log successful access
            return result

        except Exception as e:
            friendly = client_error_message(e)
            if friendly:
                return {"success": False, "error": friendly, "doctype": doctype}
            log_failure("Document List Error", e)

            return {"success": False, "error": str(e)[:2000], "doctype": doctype}


# Make sure class name matches file name for discovery
document_list = DocumentList
