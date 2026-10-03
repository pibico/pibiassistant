# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""get_account_balance on real demo ledger data."""

import frappe

from pibiassistant.plugins.core.tools.get_account_balance import GetAccountBalance
from pibiassistant.tests.base_test import BaseAssistantTest


class TestGetAccountBalance(BaseAssistantTest):
    def _run(self, **args):
        return GetAccountBalance().execute(args)

    def _gl_account(self):
        row = frappe.db.sql(
            "select account, company from `tabGL Entry` where is_cancelled=0 group by account, company limit 1",
            as_dict=True,
        )
        if not row:
            self.skipTest("no GL Entry on this site")
        return row[0]

    def test_exactly_one_mode(self):
        self.assertFalse(self._run()["success"])
        self.assertFalse(self._run(account="x", party_type="Customer", party="y")["success"])
        self.assertFalse(self._run(party_type="Customer")["success"])
        self.assertFalse(self._run(party_type="Employee", party="y")["success"])
        self.assertFalse(self._run(account="x", date="not-a-date")["success"])

    def test_account_balance_matches_ledger(self):
        from erpnext.accounts.utils import get_balance_on
        from frappe.utils import flt

        gl = self._gl_account()
        result = self._run(account=gl.account, company=gl.company)
        self.assertTrue(result["success"], result)
        acc = frappe.get_doc("Account", gl.account)
        expected = get_balance_on(
            account=gl.account, company=gl.company, in_account_currency=not acc.is_group
        )
        self.assertEqual(result["balance"], flt(expected, 2))
        self.assertTrue(result["currency"])
        self.assertIn("debit", result["sign_convention"])

    def test_account_by_number_and_unknown(self):
        gl = self._gl_account()
        number = frappe.db.get_value("Account", gl.account, "account_number")
        if number:
            result = self._run(account=number, company=gl.company)
            self.assertTrue(result["success"], result)
            self.assertEqual(result["account"], gl.account)
        self.assertFalse(self._run(account="ZZ no such account")["success"])

    def test_wrong_company_is_refused(self):
        gl = self._gl_account()
        other = frappe.db.get_value("Company", {"name": ["!=", gl.company]}, "name")
        if not other:
            self.skipTest("single company site")
        self.assertFalse(self._run(account=gl.account, company=other)["success"])

    def test_party_balance_and_outstanding(self):
        from erpnext.accounts.utils import get_balance_on
        from frappe.utils import flt

        row = frappe.db.sql(
            "select party, company from `tabGL Entry` where party_type='Customer' and is_cancelled=0 limit 1",
            as_dict=True,
        )
        if not row:
            customer = frappe.db.get_value("Customer", {}, "name")
            company = frappe.db.get_value("Company", {}, "name")
        else:
            customer, company = row[0].party, row[0].company
        result = self._run(party_type="Customer", party=customer, company=company)
        self.assertTrue(result["success"], result)
        self.assertEqual(
            result["balance"],
            flt(get_balance_on(party_type="Customer", party=customer, company=company, in_account_currency=False), 2),
        )
        self.assertIn("outstanding", result)
        self.assertLessEqual(len(result["outstanding"]), 20)
        no_out = self._run(party_type="Customer", party=customer, company=company, include_outstanding=False)
        self.assertNotIn("outstanding", no_out)

    def test_unknown_party(self):
        self.assertFalse(self._run(party_type="Customer", party="ZZ no such customer")["success"])

    def test_denied_without_ledger_permission(self):
        gl = self._gl_account()
        email = "zz-bal-t2@example.com"
        user = frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": "ZZ Bal", "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
        try:
            frappe.set_user(email)
            with self.enforce_only_for_checks():
                result = self._run(account=gl.account)
            self.assertFalse(result["success"], result)
            self.assertNotIn("balance", result)
        finally:
            frappe.set_user("Administrator")
            frappe.delete_doc("User", user.name, force=True, ignore_permissions=True)
