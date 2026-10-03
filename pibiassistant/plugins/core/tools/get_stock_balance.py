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
Stock Balance Tool for the Core Plugin.
Stock on hand by warehouse for an item, the contents of a warehouse, or a per-warehouse summary, now or as of a date.
"""

from typing import Any, Dict, List, Optional

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core import doc_actions
from pibiassistant.plugins.limits import clamp_limit
from pibiassistant.plugins.query_errors import log_failure

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
QTY_NOTE = (
    "actual_qty is what is physically in the warehouse; reserved_qty is promised to sales orders; ordered_qty "
    "is on open purchase orders; projected_qty = actual - reserved + ordered (+ planned). Values are in the "
    "company currency."
)


def _suggest_warehouses(text: str) -> List[str]:
    return frappe.get_all("Warehouse", filters={"name": ["like", f"%{text}%"]}, pluck="name", limit_page_length=5)


def _expand_warehouse(name: str) -> List[str]:
    """The warehouse, plus its descendants when it is a group."""
    if not frappe.db.get_value("Warehouse", name, "is_group"):
        return [name]
    from frappe.utils.nestedset import get_descendants_of

    return [name, *get_descendants_of("Warehouse", name)]


class GetStockBalance(BaseTool):
    """Stock levels honouring the caller's permissions (Bin, Stock Ledger Entry, Item, Warehouse)."""

    def __init__(self):
        super().__init__()
        self.name = "get_stock_balance"
        self.description = (
            "Stock on hand. With item_code: its quantity and value in every warehouse. With warehouse (a group "
            "warehouse includes its children): what it holds. With neither: a summary per warehouse. Optional "
            "date (YYYY-MM-DD) gives the balance as of that day from the stock ledger; without it, today's "
            "figures with reserved, ordered and projected quantities. Use for 'how much stock of X do we have', "
            "'what is in warehouse Y', 'stock value'. Batches are listed when an item is batch-tracked."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "item_code": {"type": "string", "description": "Item code (the Item document name)."},
                "warehouse": {"type": "string", "description": "Warehouse name; a group includes its children."},
                "date": {"type": "string", "description": "As-of date YYYY-MM-DD (ledger based). Default: now."},
                "include_zero": {"type": "boolean", "default": False, "description": "Also list rows with zero stock."},
                "limit": {"type": "integer", "default": DEFAULT_LIMIT, "description": f"Max rows, up to {MAX_LIMIT}."},
            },
            "required": [],
        }

    @staticmethod
    def _read_error(doctype: str, name: str) -> Optional[Dict[str, Any]]:
        denied = doc_actions.access_error(doctype, name, "read")
        if denied:
            return denied
        if not frappe.db.exists(doctype, name):
            return None
        try:
            if not frappe.has_permission(doctype, "read", doc=name):
                return doc_actions.fail(_("Insufficient read permissions for {0} {1}").format(doctype, name))
        except frappe.DoesNotExistError:
            return None
        return None

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        item_code = (arguments.get("item_code") or "").strip() or None
        warehouse = (arguments.get("warehouse") or "").strip() or None
        include_zero = bool(arguments.get("include_zero", False))
        limit = clamp_limit(arguments.get("limit"), DEFAULT_LIMIT, MAX_LIMIT)
        try:
            as_of = getdate(arguments.get("date")) if arguments.get("date") else None
        except Exception:
            return doc_actions.fail(_("date must be YYYY-MM-DD"))

        for doctype in ("Bin", "Item", "Warehouse") + (("Stock Ledger Entry",) if as_of else ()):
            denied = doc_actions.access_error(doctype, "", "read")
            if denied:
                return denied
            if not frappe.has_permission(doctype, "read"):
                return doc_actions.fail(_("Insufficient read permissions for {0}").format(doctype))

        if item_code:
            if not frappe.db.exists("Item", item_code):
                return doc_actions.fail(_("Item {0} not found. Use search_documents to find the item code.").format(item_code))
            error = self._read_error("Item", item_code)
            if error:
                return error
        warehouses: Optional[List[str]] = None
        if warehouse:
            if not frappe.db.exists("Warehouse", warehouse):
                suggestions = _suggest_warehouses(warehouse)
                hint = _(" Did you mean: {0}?").format(", ".join(suggestions)) if suggestions else ""
                return doc_actions.fail(_("Warehouse {0} not found.").format(warehouse) + hint)
            error = self._read_error("Warehouse", warehouse)
            if error:
                return error
            warehouses = _expand_warehouse(warehouse)

        try:
            rows = self._ledger_rows(item_code, warehouses, as_of) if as_of else self._bin_rows(item_code, warehouses)
            if not include_zero:
                rows = [r for r in rows if flt(r["actual_qty"]) != 0]
            total_rows = len(rows)
            total_qty = flt(sum(flt(r["actual_qty"]) for r in rows), 3)
            total_value = flt(sum(flt(r["stock_value"]) for r in rows), 2)
            if not item_code and not warehouse:
                rows = self._summarise_by_warehouse(rows)
                total_rows = len(rows)
            rows.sort(key=lambda r: abs(flt(r.get("stock_value"))), reverse=True)
            shown = rows[:limit]
            self._decorate(shown)
            result: Dict[str, Any] = {
                "success": True,
                "as_of": str(as_of) if as_of else str(getdate(nowdate())) + " (now)",
                "item_code": item_code,
                "warehouse": warehouse,
                "rows": shown,
                "row_count": total_rows,
                "truncated": total_rows > len(shown),
                "total_actual_qty": total_qty,
                "total_stock_value": total_value,
                "quantity_note": QTY_NOTE,
            }
            if item_code and not as_of:
                batches = self._batches(item_code, warehouses)
                if batches is not None:
                    result["batches"] = batches
            if as_of:
                result["note"] = _("Past dates come from the stock ledger: reserved, ordered and projected are not available.")
            return result
        except frappe.PermissionError:
            return doc_actions.fail(_("Insufficient read permissions for this stock balance"))
        except Exception as e:
            log_failure("Stock Balance Error", e)
            return doc_actions.fail(_("Could not compute the stock balance: {0}").format(cstr(e)[:200]))

    @staticmethod
    def _bin_rows(item_code: Optional[str], warehouses: Optional[List[str]]) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {}
        if item_code:
            filters["item_code"] = item_code
        if warehouses is not None:
            filters["warehouse"] = ["in", warehouses]
        return frappe.get_list(
            "Bin",
            filters=filters,
            fields=["item_code", "warehouse", "actual_qty", "reserved_qty", "ordered_qty", "projected_qty", "valuation_rate", "stock_value", "stock_uom"],
            limit_page_length=0,
        )

    @staticmethod
    def _ledger_rows(item_code: Optional[str], warehouses: Optional[List[str]], as_of) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {"posting_date": ["<=", as_of], "is_cancelled": 0}
        if item_code:
            filters["item_code"] = item_code
        if warehouses is not None:
            filters["warehouse"] = ["in", warehouses]
        rows = frappe.get_list(
            "Stock Ledger Entry",
            filters=filters,
            fields=["item_code", "warehouse", "sum(actual_qty) as actual_qty", "sum(stock_value_difference) as stock_value"],
            group_by="item_code, warehouse",
            limit_page_length=0,
        )
        for r in rows:
            qty = flt(r.get("actual_qty"))
            r["valuation_rate"] = flt(flt(r.get("stock_value")) / qty, 4) if qty else 0
        return rows

    @staticmethod
    def _summarise_by_warehouse(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_wh: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            wh = by_wh.setdefault(r["warehouse"], {"warehouse": r["warehouse"], "items": 0, "actual_qty": 0.0, "stock_value": 0.0})
            wh["items"] += 1
            wh["actual_qty"] += flt(r["actual_qty"])
            wh["stock_value"] += flt(r["stock_value"])
        return list(by_wh.values())

    @staticmethod
    def _decorate(rows: List[Dict[str, Any]]) -> None:
        names: Dict[str, str] = {}
        for r in rows:
            for key in ("actual_qty", "reserved_qty", "ordered_qty", "projected_qty"):
                if key in r:
                    r[key] = flt(r[key], 3)
            for key in ("stock_value", "valuation_rate"):
                if key in r:
                    r[key] = flt(r[key], 4 if key == "valuation_rate" else 2)
            code = r.get("item_code")
            if code:
                if code not in names:
                    names[code] = frappe.db.get_value("Item", code, "item_name") or ""
                r["item_name"] = names[code]

    @staticmethod
    def _batches(item_code: str, warehouses: Optional[List[str]]) -> Optional[List[Dict[str, Any]]]:
        if not frappe.db.get_value("Item", item_code, "has_batch_no"):
            return None
        from erpnext.stock.doctype.batch.batch import get_batch_qty

        out: List[Dict[str, Any]] = []
        for row in get_batch_qty(item_code=item_code) or []:
            if warehouses is not None and row.get("warehouse") not in warehouses:
                continue
            if flt(row.get("qty")):
                out.append({"batch_no": row.get("batch_no"), "warehouse": row.get("warehouse"), "qty": flt(row.get("qty"), 3)})
        return out[:MAX_LIMIT]


get_stock_balance = GetStockBalance
