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
Account Balance Tool for the Core Plugin.
Balance of a ledger account, or of a customer/supplier across the ledger, with open invoices.
"""

from typing import Any, Dict, List, Optional

import frappe
from frappe import _
from frappe.utils import cstr, date_diff, flt, getdate, nowdate

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core import doc_actions
from pibiassistant.plugins.limits import clamp_limit
from pibiassistant.plugins.query_errors import log_failure

MAX_OUTSTANDING = 20
PARTY_TYPES = ("Customer", "Supplier")
SIGN_NOTE = (
    "balance > 0 is a debit balance, < 0 a credit balance. For a Customer a positive balance is "
    "money they owe us; for a Supplier a negative balance is money we owe them."
)


class GetAccountBalance(BaseTool):
    """Balance of an account or of a party as of a date, honouring the caller's permissions."""

    def __init__(self):
        super().__init__()
        self.name = "get_account_balance"
        self.description = (
            "Balance of one ledger account (by name or account number) or of one customer/supplier, as of "
            "a date (default today), taken from the general ledger. For a party it also lists open invoices "
            "with days overdue. Use for 'what is the balance of account 572' or 'how much does customer X "
            "owe us'. Pass either account, or party_type with party. Sign: balance > 0 is debit "
            "(Customer positive = they owe us, Supplier negative = we owe them)."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account name or account number."},
                "party_type": {"type": "string", "enum": list(PARTY_TYPES), "description": "With party."},
                "party": {"type": "string", "description": "Customer or Supplier name (the document name)."},
                "company": {"type": "string", "description": "Company. Default: the user's default company."},
                "date": {"type": "string", "description": "As-of date YYYY-MM-DD. Default today."},
                "include_outstanding": {
                    "type": "boolean",
                    "default": True,
                    "description": "Party mode: also list open invoices (max 20).",
                },
            },
            "required": [],
        }

    @staticmethod
    def _read_error(doctype: str, name: str) -> Optional[Dict[str, Any]]:
        denied = doc_actions.access_error(doctype, name, "read")
        if denied:
            return denied
        if not frappe.db.exists(doctype, name):
            return doc_actions.fail(_("{0} {1} not found").format(doctype, name))
        try:
            if not frappe.has_permission(doctype, "read", doc=name):
                return doc_actions.fail(_("Insufficient read permissions for {0} {1}").format(doctype, name))
        except frappe.DoesNotExistError:
            return doc_actions.fail(_("{0} {1} not found").format(doctype, name))
        return None

    @staticmethod
    def _resolve_account(value: str, company: Optional[str]) -> Dict[str, Any]:
        if frappe.db.exists("Account", value):
            return {"name": value}
        filters = {"account_number": value}
        if company:
            filters["company"] = company
        matches = frappe.get_all("Account", filters=filters, pluck="name", limit_page_length=3)
        if not matches:
            return doc_actions.fail(_("Account {0} not found").format(value))
        if len(matches) > 1:
            return doc_actions.fail(_("Account number {0} exists in several companies; pass company").format(value))
        return {"name": matches[0]}

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        account = (arguments.get("account") or "").strip() or None
        party_type = arguments.get("party_type") or None
        party = (arguments.get("party") or "").strip() or None
        company = (arguments.get("company") or "").strip() or None
        include_outstanding = arguments.get("include_outstanding", True)

        if bool(account) == bool(party_type or party):
            return doc_actions.fail(_("Pass either account, or party_type together with party."))
        if not account and not (party_type and party):
            return doc_actions.fail(_("party_type and party must be given together."))
        if party_type and party_type not in PARTY_TYPES:
            return doc_actions.fail(_("party_type must be one of: {0}").format(", ".join(PARTY_TYPES)))
        try:
            as_of = getdate(arguments.get("date")) if arguments.get("date") else getdate(nowdate())
        except Exception:
            return doc_actions.fail(_("date must be YYYY-MM-DD"))

        denied = doc_actions.access_error("GL Entry", "", "read")
        if denied:
            return denied
        if not frappe.has_permission("GL Entry", "read"):
            return doc_actions.fail(_("Insufficient read permissions for {0}").format("GL Entry"))

        if not company:
            company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
                "Global Defaults", "default_company"
            )
        if company:
            error = self._read_error("Company", company)
            if error:
                return error

        try:
            if account:
                return self._account_result(account, company, as_of)
            return self._party_result(party_type, party, company, as_of, include_outstanding)
        except frappe.PermissionError:
            return doc_actions.fail(_("Insufficient read permissions for this balance"))
        except Exception as e:
            log_failure("Account Balance Error", e)
            return doc_actions.fail(_("Could not compute the balance: {0}").format(cstr(e)[:200]))

    def _account_result(self, value: str, company: Optional[str], as_of) -> Dict[str, Any]:
        from erpnext.accounts.utils import get_balance_on

        resolved = self._resolve_account(value, company)
        if resolved.get("success") is False:
            return resolved
        name = resolved["name"]
        error = self._read_error("Account", name)
        if error:
            return error
        acc = frappe.get_cached_doc("Account", name)
        if company and acc.company != company:
            return doc_actions.fail(_("Account {0} belongs to {1}, not {2}").format(name, acc.company, company))
        company_currency = frappe.get_cached_value("Company", acc.company, "default_currency")
        # Group accounts add up children that may use other currencies; report them in company currency.
        in_account_currency = not acc.is_group
        balance = get_balance_on(
            account=name, date=as_of, company=acc.company, in_account_currency=in_account_currency
        )
        return {
            "success": True,
            "account": name,
            "account_number": acc.account_number,
            "is_group": bool(acc.is_group),
            "company": acc.company,
            "balance": flt(balance, 2),
            "currency": (acc.account_currency or company_currency) if in_account_currency else company_currency,
            "as_of": str(as_of),
            "sign_convention": SIGN_NOTE,
        }

    def _party_result(self, party_type, party, company, as_of, include_outstanding) -> Dict[str, Any]:
        from erpnext.accounts.party import get_party_account
        from erpnext.accounts.utils import get_balance_on, get_outstanding_invoices

        error = self._read_error(party_type, party)
        if error:
            return error
        if not company:
            return doc_actions.fail(_("No company given and the user has no default company."))
        currency = frappe.get_cached_value("Company", company, "default_currency")
        balance = get_balance_on(
            date=as_of, party_type=party_type, party=party, company=company, in_account_currency=False
        )
        result: Dict[str, Any] = {
            "success": True,
            "party_type": party_type,
            "party": party,
            "party_name": frappe.db.get_value(party_type, party, f"{party_type.lower()}_name"),
            "company": company,
            "balance": flt(balance, 2),
            "currency": currency,
            "as_of": str(as_of),
            "sign_convention": SIGN_NOTE,
        }
        if include_outstanding:
            # The ledger helper only reports invoices open today, so ageing is measured from today.
            today = getdate(nowdate())
            outstanding: List[Dict[str, Any]] = []
            total = 0
            party_account = get_party_account(party_type, party, company)
            if party_account:
                rows = get_outstanding_invoices(party_type, party, [party_account])
                total = len(rows)
                for r in rows[:MAX_OUTSTANDING]:
                    due = r.get("due_date")
                    outstanding.append(
                        {
                            "voucher_type": r.get("voucher_type"),
                            "voucher_no": r.get("voucher_no"),
                            "posting_date": str(r.get("posting_date")),
                            "due_date": str(due) if due else None,
                            "outstanding_amount": flt(r.get("outstanding_amount"), 2),
                            "currency": r.get("currency") or currency,
                            "days_overdue": max(date_diff(today, due), 0) if due else 0,
                        }
                    )
            result["outstanding"] = outstanding
            result["outstanding_as_of"] = str(today)
            result["outstanding_count"] = total
            result["outstanding_truncated"] = total > len(outstanding)
        return result


get_account_balance = GetAccountBalance
