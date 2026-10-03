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
Journal Entry Tool for the Core Plugin.
Creates a balanced manual accounting entry as a DRAFT; submitting it stays a separate, explicit step.
"""

from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core.doc_actions import access_error, document_url, fail
from pibiassistant.plugins.query_errors import log_failure

VOUCHER_TYPES = ("Journal Entry", "Bank Entry", "Cash Entry", "Credit Card Entry", "Contra Entry", "Debit Note", "Credit Note")
PARTY_ACCOUNT_TYPES = ("Receivable", "Payable")
PARTY_TYPES = ("Customer", "Supplier", "Employee", "Shareholder")
MAX_LINES = 40
MAX_REMARK = 1000


def _amount(value: Any) -> Optional[float]:
    if value in (None, "", 0, "0"):
        return 0.0
    try:
        number = flt(value, 2)
    except Exception:
        return None
    return number if number >= 0 else None


def _resolve_account(value: str, company: str) -> Optional[frappe._dict]:
    """The account row named by its name or account number inside the company."""
    fields = ["name", "account_type", "account_currency", "is_group", "disabled", "company", "account_number"]
    row = frappe.db.get_value("Account", {"name": value, "company": company}, fields, as_dict=True)
    if not row:
        row = frappe.db.get_value("Account", {"account_number": value, "company": company}, fields, as_dict=True)
    return row


def check_entry(arguments: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
    """(error, normalised entry). Checks everything that can be checked without writing; runs before the approval
    card and again at execution."""
    asked = (arguments.get("company") or "").strip()
    company = asked or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
    company_note = ""
    if not company or not frappe.db.exists("Company", company):
        companies = frappe.get_all("Company", pluck="name", limit_page_length=10)
        if len(companies) == 1:
            # A model often invents or mistypes the optional company; with only one there is nothing to confuse it with.
            company = companies[0]
            if asked:
                company_note = _("Company {0} does not exist; used the only company, {1}.").format(asked, company)
        else:
            return _("Company {0} not found. Omit company or use one of: {1}").format(company or "-", ", ".join(companies)), {}
    voucher_type = (arguments.get("voucher_type") or "Journal Entry").strip()
    if voucher_type not in VOUCHER_TYPES:
        return _("voucher_type must be one of: {0}").format(", ".join(VOUCHER_TYPES)), {}
    try:
        posting_date = getdate(arguments.get("posting_date")) if arguments.get("posting_date") else getdate(nowdate())
    except Exception:
        return _("posting_date must be YYYY-MM-DD"), {}
    remark = cstr(arguments.get("remark") or arguments.get("user_remark") or "").strip()[:MAX_REMARK]

    lines = arguments.get("accounts")
    if not isinstance(lines, list) or len(lines) < 2:
        return _("An entry needs at least two lines in accounts (account plus debit or credit)."), {}
    if len(lines) > MAX_LINES:
        return _("At most {0} lines per entry.").format(MAX_LINES), {}

    currency = frappe.get_cached_value("Company", company, "default_currency")
    rows: List[Dict[str, Any]] = []
    total_debit = total_credit = 0.0
    for index, line in enumerate(lines, start=1):
        if not isinstance(line, dict) or not line.get("account"):
            return _("Line {0}: account is required.").format(index), {}
        account = _resolve_account(cstr(line["account"]).strip(), company)
        if not account:
            return _("Line {0}: account {1} does not exist in {2}. Use search_documents on Account to find it.").format(index, line["account"], company), {}
        if account.is_group:
            return _("Line {0}: {1} is a group account; post to one of its sub-accounts.").format(index, account.name), {}
        if account.disabled:
            return _("Line {0}: account {1} is disabled.").format(index, account.name), {}
        if account.account_currency and account.account_currency != currency:
            return _("Line {0}: {1} is in {2}; only {3} accounts are supported here.").format(index, account.name, account.account_currency, currency), {}
        debit, credit = _amount(line.get("debit")), _amount(line.get("credit"))
        if debit is None or credit is None:
            return _("Line {0}: debit and credit must be numbers of zero or more.").format(index), {}
        if (debit > 0) == (credit > 0):
            return _("Line {0}: give exactly one of debit or credit (greater than zero).").format(index), {}
        party_type, party = cstr(line.get("party_type")).strip(), cstr(line.get("party")).strip()
        if account.account_type in PARTY_ACCOUNT_TYPES:
            if not (party_type and party):
                return _("Line {0}: {1} is a {2} account: party_type and party are required.").format(index, account.name, account.account_type), {}
            if party_type not in PARTY_TYPES:
                return _("Line {0}: party_type must be one of: {1}").format(index, ", ".join(PARTY_TYPES)), {}
            if not frappe.db.exists(party_type, party):
                return _("Line {0}: {1} {2} not found.").format(index, party_type, party), {}
        elif party_type or party:
            return _("Line {0}: party is only allowed on Receivable or Payable accounts.").format(index), {}
        cost_center = cstr(line.get("cost_center")).strip()
        if cost_center and frappe.db.get_value("Cost Center", cost_center, "company") != company:
            return _("Line {0}: cost center {1} not found in {2}.").format(index, cost_center, company), {}
        total_debit += debit
        total_credit += credit
        row = {"account": account.name, "debit_in_account_currency": debit, "credit_in_account_currency": credit}
        if party:
            row.update({"party_type": party_type, "party": party})
        if cost_center:
            row["cost_center"] = cost_center
        if line.get("remark") or line.get("user_remark"):
            row["user_remark"] = cstr(line.get("remark") or line.get("user_remark"))[:MAX_REMARK]
        rows.append(row)

    if flt(total_debit - total_credit, 2) != 0:
        return _("The entry does not balance: debits {0:.2f}, credits {1:.2f} (difference {2:.2f}).").format(total_debit, total_credit, total_debit - total_credit), {}
    if total_debit <= 0:
        return _("The entry has no amounts."), {}
    return None, {
        "company": company, "voucher_type": voucher_type, "posting_date": str(posting_date), "user_remark": remark,
        "accounts": rows, "total": flt(total_debit, 2), "currency": currency, "company_note": company_note,
    }


def preview(arguments: Dict[str, Any]) -> str:
    error, entry = check_entry(arguments)
    if error:
        return f"Journal entry. Will be refused: {error}"
    shown = "; ".join(
        f"{'Dr' if r['debit_in_account_currency'] else 'Cr'} {r['account']} {(r['debit_in_account_currency'] or r['credit_in_account_currency']):.2f}"
        for r in entry["accounts"][:6]
    )
    more = f" (+{len(entry['accounts']) - 6} more lines)" if len(entry["accounts"]) > 6 else ""
    return (
        f"Create a DRAFT {entry['voucher_type']} on {entry['posting_date']} for {entry['total']:.2f} {entry['currency']}: "
        f"{shown}{more}. Nothing is posted until it is submitted." + (f" {entry['company_note']}" if entry.get("company_note") else "")
    )


class JournalEntryCreate(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "create_journal_entry"
        self.description = (
            "Create a manual accounting entry (asiento) as a DRAFT Journal Entry: lines of account plus debit or "
            "credit that must balance exactly, e.g. a reclassification, an accrual or a correction. Accounts are "
            "leaf accounts of the company in its currency (name or account number); Receivable/Payable accounts "
            "need party_type and party. It is saved as a draft and posts nothing: tell the user the entry name "
            "and let them review it, then submit_document posts it. For invoices and payments use their own "
            "documents instead. Needs the user's approval."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "accounts": {
                    "type": "array",
                    "description": f"2 to {MAX_LINES} lines; total debits must equal total credits.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "account": {"type": "string", "description": "Account name or account number."},
                            "debit": {"type": "number", "description": "Amount debited (give debit or credit, not both)."},
                            "credit": {"type": "number", "description": "Amount credited."},
                            "party_type": {"type": "string", "enum": list(PARTY_TYPES)},
                            "party": {"type": "string", "description": "Required on Receivable/Payable accounts."},
                            "cost_center": {"type": "string"},
                            "remark": {"type": "string", "description": "Line note (optional)."},
                        },
                        "required": ["account"],
                    },
                },
                "posting_date": {"type": "string", "description": "YYYY-MM-DD, default today."},
                "voucher_type": {"type": "string", "enum": list(VOUCHER_TYPES), "default": "Journal Entry"},
                "company": {"type": "string", "description": "Omit unless the user names a company; default: the user's default company."},
                "remark": {"type": "string", "description": "Description of the entry (shown in the ledger)."},
            },
            "required": ["accounts"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        error, entry = check_entry(arguments)
        if error:
            return fail(error)
        blocked = access_error("Journal Entry", "", "create")
        if blocked:
            return blocked
        try:
            if not frappe.has_permission("Journal Entry", "create"):
                return fail(_("You do not have permission to create journal entries."), permission_error=True)
            doc = frappe.get_doc(
                {
                    "doctype": "Journal Entry", "voucher_type": entry["voucher_type"], "company": entry["company"],
                    "posting_date": entry["posting_date"], "user_remark": entry["user_remark"], "accounts": entry["accounts"],
                }
            )
            doc.insert()
            frappe.db.commit()
            return {
                "success": True, "doctype": "Journal Entry", "name": doc.name, "docstatus": doc.docstatus,
                "total_debit": flt(doc.total_debit, 2), "total_credit": flt(doc.total_credit, 2), "currency": entry["currency"],
                "url": document_url("Journal Entry", doc.name),
                "message": f"Draft {doc.name} created and nothing is posted yet. Review it and use submit_document to post it."
                + (f" {entry['company_note']}" if entry.get("company_note") else ""),
            }
        except frappe.PermissionError:
            return fail(_("You do not have permission to create journal entries."), permission_error=True)
        except Exception as e:
            frappe.db.rollback()
            log_failure("Journal Entry Error", e)
            return fail(cstr(e)[:400] or _("Could not create the journal entry."))


create_journal_entry = JournalEntryCreate
