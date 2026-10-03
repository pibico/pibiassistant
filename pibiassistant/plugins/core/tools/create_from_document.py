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

"""Create a draft document from another one (Quotation -> Sales Order -> Invoice ...), the way the Desk's Create menu does."""

from typing import Any, Dict, Optional

import frappe

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core.doc_actions import access_error, document_url, fail
from pibiassistant.plugins.query_errors import log_failure

# (source DocType, target DocType) -> (ERPNext method, call style). Only these pairs are offered: each is a
# standard Create-menu action, so the line items and links are mapped by ERPNext itself.
_STD = "std"  # method(source_name) -> unsaved target doc
_PAY = "payment"  # method(source_doctype, source_name) -> unsaved Payment Entry
SELLING = "erpnext.selling.doctype"
BUYING = "erpnext.buying.doctype"
PAIRS: Dict[tuple, tuple] = {
    ("Quotation", "Sales Order"): (f"{SELLING}.quotation.quotation.make_sales_order", _STD),
    ("Quotation", "Sales Invoice"): (f"{SELLING}.quotation.quotation.make_sales_invoice", _STD),
    ("Sales Order", "Sales Invoice"): (f"{SELLING}.sales_order.sales_order.make_sales_invoice", _STD),
    ("Sales Order", "Delivery Note"): (f"{SELLING}.sales_order.sales_order.make_delivery_note", _STD),
    ("Delivery Note", "Sales Invoice"): ("erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice", _STD),
    ("Supplier Quotation", "Purchase Order"): (f"{BUYING}.supplier_quotation.supplier_quotation.make_purchase_order", _STD),
    ("Purchase Order", "Purchase Invoice"): (f"{BUYING}.purchase_order.purchase_order.make_purchase_invoice", _STD),
    ("Purchase Order", "Purchase Receipt"): (f"{BUYING}.purchase_order.purchase_order.make_purchase_receipt", _STD),
    ("Purchase Receipt", "Purchase Invoice"): ("erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice", _STD),
    ("Opportunity", "Quotation"): ("erpnext.crm.doctype.opportunity.opportunity.make_quotation", _STD),
    ("Lead", "Opportunity"): ("erpnext.crm.doctype.lead.lead.make_opportunity", _STD),
    ("Sales Invoice", "Payment Entry"): ("erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry", _PAY),
    ("Sales Order", "Payment Entry"): ("erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry", _PAY),
    ("Purchase Invoice", "Payment Entry"): ("erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry", _PAY),
    ("Purchase Order", "Payment Entry"): ("erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry", _PAY),
}


def available_targets(source_doctype: str) -> list:
    return sorted(target for (source, target) in PAIRS if source == source_doctype)


def check_create(source_doctype: str, source_name: str, target_doctype: str) -> Optional[str]:
    if not source_doctype or not source_name or not target_doctype:
        return "source_doctype, source_name and target_doctype are required"
    if (source_doctype, target_doctype) not in PAIRS:
        targets = available_targets(source_doctype)
        if targets:
            return f"A {source_doctype} can be turned into: {', '.join(targets)}. Not into {target_doctype}."
        pairs = sorted({s for s, _t in PAIRS})
        return f"{source_doctype} has no supported conversion. Supported sources: {', '.join(pairs)}."
    if not frappe.db.exists(source_doctype, source_name):
        return f"{source_doctype} '{source_name}' not found"
    return None


def preview(arguments: Dict[str, Any]) -> str:
    source, name, target = arguments.get("source_doctype"), arguments.get("source_name"), arguments.get("target_doctype")
    problem = check_create(source, name, target)
    if problem:
        return f"{source} '{name}' -> {target}. Will be refused: {problem}"
    return f"Create a draft {target} from {source} '{name}'; items and links are mapped by ERPNext. Nothing is submitted."


class DocumentCreateFrom(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "create_from_document"
        self.description = (
            "Create a DRAFT document from an existing one, like the Create menu in the Desk, so line items, "
            "customer and links are copied by ERPNext instead of by hand. Supported: Quotation -> Sales Order or "
            "Sales Invoice; Sales Order -> Sales Invoice, Delivery Note or Payment Entry; Delivery Note -> Sales "
            "Invoice; Sales Invoice -> Payment Entry; Supplier Quotation -> Purchase Order; Purchase Order -> "
            "Purchase Invoice, Purchase Receipt or Payment Entry; Purchase Receipt -> Purchase Invoice; Purchase "
            "Invoice -> Payment Entry; Opportunity -> Quotation; Lead -> Opportunity. A Sales Order also needs "
            "delivery_date. The source usually has to be submitted. The result is a saved draft: review it and use submit_document to submit it. "
            "Needs the user's approval."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "source_doctype": {"type": "string", "description": "DocType of the existing document (e.g. 'Quotation')"},
                "source_name": {"type": "string", "description": "Name/ID of the existing document"},
                "target_doctype": {"type": "string", "description": "DocType to create (e.g. 'Sales Order')"},
                "delivery_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD. Required when creating a Sales Order (ERPNext needs a delivery date): ask the user if they did not say",
                },
            },
            "required": ["source_doctype", "source_name", "target_doctype"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        source, name, target = arguments.get("source_doctype"), arguments.get("source_name"), arguments.get("target_doctype")
        problem = check_create(source, name, target)
        if problem:
            return fail(problem, source_doctype=source, source_name=name, target_doctype=target)
        blocked = access_error(target, "", "create")
        if blocked:
            return blocked
        try:
            if not frappe.has_permission(source, "read", doc=name):
                return fail(f"Insufficient permissions to read {source} '{name}'", permission_error=True)
            if not frappe.has_permission(target, "create"):
                return fail(f"Insufficient permissions to create {target}", permission_error=True)
            method, style = PAIRS[(source, target)]
            func = frappe.get_attr(method)
            doc = func(source, name) if style == _PAY else func(name)
            delivery_date = str(arguments.get("delivery_date") or "")[:10]
            if target == "Sales Order" and delivery_date:
                doc.delivery_date = delivery_date
                for row in doc.get("items") or []:
                    row.delivery_date = delivery_date
            if target == "Sales Order" and not (doc.get("delivery_date") or all(r.get("delivery_date") for r in doc.get("items") or [])):
                return fail(
                    "A Sales Order needs a delivery date. Ask the user for it and call again with delivery_date (YYYY-MM-DD).",
                    source_doctype=source, source_name=name, target_doctype=target, needs="delivery_date",
                )
            doc.insert()
            frappe.db.commit()
            return {
                "success": True, "source_doctype": source, "source_name": name, "doctype": target, "name": doc.name,
                "docstatus": doc.docstatus, "url": document_url(target, doc.name),
                "message": f"Draft {target} {doc.name} created from {source} '{name}'. Review it and submit it when ready.",
            }
        except frappe.PermissionError:
            return fail(f"Insufficient permissions to create {target} from {source} '{name}'", permission_error=True)
        except Exception as e:
            frappe.db.rollback()
            log_failure("Document Create From Error", e)
            return fail(str(e) or f"Could not create {target} from {source} '{name}'",
                        source_doctype=source, source_name=name, target_doctype=target)


document_create_from = DocumentCreateFrom
