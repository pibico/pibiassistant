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
Overdue Invoices Tool for the Core Plugin.
Unpaid invoices past their due date with ageing buckets, through the permission-aware list API.
"""

from typing import Any, Dict, List

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, nowdate

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core import doc_actions
from pibiassistant.plugins.limits import clamp_limit
from pibiassistant.plugins.query_errors import log_failure, permission_error_result

MAX_LIMIT = 200
FETCH_CAP = 1000
MAX_PARTIES = 50
BUCKETS = ("1-30", "31-60", "61-90", "90+")
KINDS = {
    "Customer": {"doctype": "Sales Invoice", "party": "customer", "name": "customer_name"},
    "Supplier": {"doctype": "Purchase Invoice", "party": "supplier", "name": "supplier_name"},
}


def bucket_for(days: int) -> str:
    if days <= 30:
        return BUCKETS[0]
    if days <= 60:
        return BUCKETS[1]
    if days <= 90:
        return BUCKETS[2]
    return BUCKETS[3]


class GetOverdueInvoices(BaseTool):
    """Unpaid overdue sales or purchase invoices with ageing, limited to what the caller may read."""

    def __init__(self):
        super().__init__()
        self.name = "get_overdue_invoices"
        self.description = (
            "Unpaid invoices past their due date with ageing buckets (1-30, 31-60, 61-90, 90+ days), totals "
            "per currency and the parties owing the most. party_type Customer reads Sales Invoices (what "
            "customers owe us), Supplier reads Purchase Invoices (what we owe). Optional party, company and "
            "as-of date. Use for 'who is late paying', 'overdue receivables' or 'overdue payables'."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "party_type": {"type": "string", "enum": list(KINDS), "default": "Customer"},
                "party": {"type": "string", "description": "Only this customer/supplier."},
                "company": {"type": "string"},
                "as_of": {"type": "string", "description": "Date YYYY-MM-DD. Default today."},
                "min_days_overdue": {"type": "integer", "default": 1, "description": "Only invoices at least this late."},
                "limit": {"type": "integer", "default": 50, "maximum": MAX_LIMIT, "description": "Invoices listed."},
            },
            "required": [],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        party_type = arguments.get("party_type") or "Customer"
        if party_type not in KINDS:
            return doc_actions.fail(_("party_type must be one of: {0}").format(", ".join(KINDS)))
        kind = KINDS[party_type]
        doctype = kind["doctype"]
        try:
            as_of = getdate(arguments.get("as_of")) if arguments.get("as_of") else getdate(nowdate())
        except Exception:
            return doc_actions.fail(_("as_of must be YYYY-MM-DD"))
        min_days = max(cint(arguments.get("min_days_overdue", 1)), 1)
        limit = clamp_limit(arguments.get("limit"), 50, MAX_LIMIT)

        denied = doc_actions.access_error(doctype, "", "read")
        if denied:
            return denied

        filters: Dict[str, Any] = {
            "docstatus": 1,
            "is_return": 0,
            "outstanding_amount": [">", 0],
            "due_date": ["<=", str(add_days(as_of, -min_days))],
        }
        if arguments.get("party"):
            filters[kind["party"]] = arguments["party"]
        if arguments.get("company"):
            filters["company"] = arguments["company"]

        try:
            rows = frappe.get_list(
                doctype,
                filters=filters,
                fields=[
                    "name",
                    f"{kind['party']} as party",
                    f"{kind['name']} as party_name",
                    "posting_date",
                    "due_date",
                    "outstanding_amount",
                    "currency",
                    "company",
                ],
                order_by="due_date asc, name asc",
                limit_page_length=FETCH_CAP + 1,
                ignore_permissions=False,
            )
        except frappe.PermissionError as e:
            return permission_error_result(e, _("Insufficient read permissions for {0}").format(doctype))
        except Exception as e:
            log_failure("Overdue Invoices Error", e)
            return doc_actions.fail(_("Could not read the overdue invoices"))

        truncated = len(rows) > FETCH_CAP
        rows = rows[:FETCH_CAP]

        totals: Dict[str, float] = {}
        buckets: Dict[str, Dict[str, Dict[str, Any]]] = {b: {} for b in BUCKETS}
        parties: Dict[Any, Dict[str, Any]] = {}
        invoices: List[Dict[str, Any]] = []
        for row in rows:
            days = date_diff(as_of, row.due_date)
            amount = flt(row.outstanding_amount)
            currency = row.currency or ""
            totals[currency] = totals.get(currency, 0) + amount
            cell = buckets[bucket_for(days)].setdefault(currency, {"count": 0, "amount": 0})
            cell["count"] += 1
            cell["amount"] += amount
            entry = parties.setdefault(
                (row.party, currency),
                {
                    "party": row.party,
                    "name": row.party_name,
                    "currency": currency,
                    "invoices": 0,
                    "outstanding": 0,
                    "oldest_days": 0,
                },
            )
            entry["invoices"] += 1
            entry["outstanding"] += amount
            entry["oldest_days"] = max(entry["oldest_days"], days)
            if len(invoices) < limit:
                invoices.append(
                    {
                        "name": row.name,
                        "party": row.party,
                        "party_name": row.party_name,
                        "posting_date": str(row.posting_date),
                        "due_date": str(row.due_date),
                        "days_overdue": days,
                        "outstanding_amount": flt(amount, 2),
                        "currency": currency,
                        "company": row.company,
                    }
                )

        for cells in buckets.values():
            for cell in cells.values():
                cell["amount"] = flt(cell["amount"], 2)
        ranked = sorted(parties.values(), key=lambda p: p["outstanding"], reverse=True)
        for p in ranked:
            p["outstanding"] = flt(p["outstanding"], 2)

        return {
            "success": True,
            "party_type": party_type,
            "doctype": doctype,
            "as_of": str(as_of),
            "total_count": len(rows),
            "truncated": truncated,
            "totals_by_currency": {c: flt(a, 2) for c, a in totals.items()},
            "buckets": buckets,
            "parties": ranked[:MAX_PARTIES],
            "invoices": invoices,
            "invoices_shown": len(invoices),
        }


get_overdue_invoices = GetOverdueInvoices
