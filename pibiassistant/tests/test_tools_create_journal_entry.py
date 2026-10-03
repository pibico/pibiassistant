# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""create_journal_entry on real accounts of the demo company: always a balanced draft, nothing posted."""

import unittest
from unittest import mock

import frappe
from frappe.utils import flt

from pibiassistant.pibiassistant_chat.api.chat.aida_tools import WRITE_TOOLS, _approval_card
from pibiassistant.plugins.core.tools.create_journal_entry import JournalEntryCreate, check_entry

MARK = "ZZ-JE-TEST"


class TestCreateJournalEntry(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.lang = frappe.local.lang
        frappe.local.lang = "en"
        self.company = frappe.db.get_value("Company", {}, "name")
        currency = frappe.get_cached_value("Company", self.company, "default_currency") if self.company else None
        accounts = frappe.get_all(
            "Account", filters={"company": self.company, "is_group": 0, "disabled": 0, "account_type": ["in", ["", None]]},
            fields=["name", "account_number", "account_currency"], limit_page_length=20,
        ) if self.company else []
        self.plain = [a for a in accounts if not a.account_currency or a.account_currency == currency]
        if len(self.plain) < 2:
            self.skipTest("the site has no two plain leaf accounts")
        self.a, self.b = self.plain[0], self.plain[1]
        self.created = []

    def tearDown(self):
        frappe.local.lang = self.lang
        frappe.set_user("Administrator")
        for name in self.created + frappe.get_all("Journal Entry", filters={"user_remark": ["like", f"{MARK}%"]}, pluck="name"):
            if frappe.db.exists("Journal Entry", name):
                doc = frappe.get_doc("Journal Entry", name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Journal Entry", name, force=True, ignore_permissions=True)
        frappe.db.commit()

    def _args(self, **extra):
        base = {
            "company": self.company, "remark": f"{MARK} reclass",
            "accounts": [{"account": self.a.name, "debit": 12.34}, {"account": self.b.name, "credit": 12.34}],
        }
        base.update(extra)
        return base

    def test_creates_a_balanced_draft_and_posts_nothing(self):
        gl_before = frappe.db.count("GL Entry")
        result = JournalEntryCreate().execute(self._args())
        self.assertTrue(result["success"], result)
        self.created.append(result["name"])
        self.assertEqual(result["docstatus"], 0)
        self.assertEqual(result["total_debit"], 12.34)
        self.assertEqual(result["total_credit"], 12.34)
        doc = frappe.get_doc("Journal Entry", result["name"])
        self.assertEqual([flt(r.debit_in_account_currency) for r in doc.accounts], [12.34, 0])
        self.assertTrue(doc.user_remark.startswith(MARK))
        self.assertEqual(frappe.db.count("GL Entry"), gl_before)

    def test_account_number_resolves(self):
        number = next((a for a in self.plain if a.account_number), None)
        if not number:
            self.skipTest("no account number in use")
        other = next(a for a in self.plain if a.name != number.name)
        err, entry = check_entry({"company": self.company, "accounts": [{"account": number.account_number, "debit": 1}, {"account": other.name, "credit": 1}]})
        self.assertIsNone(err, err)
        self.assertEqual(entry["accounts"][0]["account"], number.name)

    def test_refusals(self):
        def refused(accounts, text, **extra):
            err, _entry = check_entry({"company": self.company, "accounts": accounts, **extra})
            self.assertIsNotNone(err, text)
            self.assertIn(text, err, err)

        refused([{"account": self.a.name, "debit": 5}], "at least two lines")
        refused([{"account": self.a.name, "debit": 5}, {"account": self.b.name, "credit": 4}], "does not balance")
        refused([{"account": self.a.name, "debit": 5, "credit": 5}, {"account": self.b.name, "credit": 0}], "exactly one")
        refused([{"account": self.a.name}, {"account": self.b.name, "credit": 1}], "exactly one")
        refused([{"account": self.a.name, "debit": -5}, {"account": self.b.name, "credit": -5}], "numbers of zero or more")
        refused([{"account": "ZZ no such account", "debit": 5}, {"account": self.b.name, "credit": 5}], "does not exist")
        refused([{"account": self.a.name, "debit": 5}, {"account": self.b.name, "credit": 5}], "voucher_type", voucher_type="Made Up")
        refused([{"account": self.a.name, "debit": 5}, {"account": self.b.name, "credit": 5}], "posting_date", posting_date="not-a-date")
        refused([{"account": self.a.name, "debit": 5, "party_type": "Customer", "party": "x"}, {"account": self.b.name, "credit": 5}], "only allowed on Receivable")
        refused([{"account": self.a.name, "debit": 5}] * 41, "At most")

    def test_group_accounts_and_party_rules(self):
        group = frappe.db.get_value("Account", {"company": self.company, "is_group": 1}, "name")
        if group:
            err, _e = check_entry({"company": self.company, "accounts": [{"account": group, "debit": 1}, {"account": self.b.name, "credit": 1}]})
            self.assertIn("group account", err)
        receivable = frappe.db.get_value("Account", {"company": self.company, "account_type": "Receivable", "is_group": 0, "disabled": 0}, "name")
        if receivable:
            err, _e = check_entry({"company": self.company, "accounts": [{"account": receivable, "debit": 1}, {"account": self.b.name, "credit": 1}]})
            self.assertIn("party_type and party are required", err)

    def test_a_mistyped_company_is_ignored_on_a_single_company_site(self):
        accounts = [{"account": self.a.name, "debit": 3}, {"account": self.b.name, "credit": 3}]
        if frappe.db.count("Company") != 1:
            self.skipTest("needs a single-company site")
        err, entry = check_entry({"company": "Compania que no existe SL", "accounts": accounts})
        self.assertIsNone(err, err)
        self.assertEqual(entry["company"], self.company)
        self.assertIn("used the only company", entry["company_note"])
        result = JournalEntryCreate().execute({"company": "Compania que no existe SL", "remark": f"{MARK} company", "accounts": accounts})
        self.assertTrue(result["success"], result)
        self.created.append(result["name"])
        self.assertIn("used the only company", result["message"])

    def test_several_companies_stay_strict_and_list_the_valid_ones(self):
        accounts = [{"account": self.a.name, "debit": 3}, {"account": self.b.name, "credit": 3}]
        with mock.patch.object(frappe, "get_all", return_value=["Alpha SL", "Beta SL"]):
            err, _entry = check_entry({"company": "Gamma SL", "accounts": accounts})
        self.assertIn("not found", err)
        self.assertIn("Alpha SL, Beta SL", err)

    def test_no_permission_no_entry(self):
        frappe.set_user("Guest")
        try:
            result = JournalEntryCreate().execute(self._args())
        finally:
            frappe.set_user("Administrator")
        self.assertFalse(result["success"])
        self.assertFalse(frappe.db.exists("Journal Entry", {"user_remark": ["like", f"{MARK}%"]}))

    def test_chat_policy_and_card_preview(self):
        self.assertIn("create_journal_entry", WRITE_TOOLS)
        card = _approval_card({"interrupt_id": "i1", "name": "create_journal_entry", "arguments": self._args()})
        text = card["reason"]["description"]
        self.assertIn("DRAFT Journal Entry", text)
        self.assertIn("12.34", text)
        self.assertIn(self.a.name, text)
        self.assertTrue(card["reason"]["action"].startswith("Create a journal entry"))
        bad = _approval_card({"interrupt_id": "i2", "name": "create_journal_entry", "arguments": {"accounts": []}})
        self.assertIn("Will be refused", bad["reason"]["description"])
