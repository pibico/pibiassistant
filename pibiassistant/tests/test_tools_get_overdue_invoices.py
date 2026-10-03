# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""get_overdue_invoices: ageing maths on patched rows, empty structure on the real site."""

from unittest.mock import patch

import frappe

from pibiassistant.plugins.core.tools.get_overdue_invoices import GetOverdueInvoices, bucket_for
from pibiassistant.tests.base_test import BaseAssistantTest


def _row(name, party, due, amount, currency="EUR"):
    return frappe._dict(
        name=name,
        party=party,
        party_name=party.title(),
        posting_date="2026-01-01",
        due_date=due,
        outstanding_amount=amount,
        currency=currency,
        company="ZZ Co",
    )


class TestGetOverdueInvoices(BaseAssistantTest):
    def _run(self, rows=None, **args):
        args.setdefault("as_of", "2026-10-01")
        if rows is None:
            return GetOverdueInvoices().execute(args)
        with patch("frappe.get_list", return_value=rows) as gl:
            result = GetOverdueInvoices().execute(args)
        self.get_list_call = gl.call_args
        return result

    def test_bucket_edges(self):
        self.assertEqual([bucket_for(d) for d in (1, 30, 31, 60, 61, 90, 91)], ["1-30", "1-30", "31-60", "31-60", "61-90", "61-90", "90+"])

    def test_ageing_totals_and_parties(self):
        rows = [
            _row("SINV-1", "acme", "2026-09-25", 100),  # 6 days
            _row("SINV-2", "acme", "2026-08-01", 250.5),  # 61 days
            _row("SINV-3", "beta", "2026-05-01", 40, "USD"),  # 153 days
        ]
        r = self._run(rows)
        self.assertTrue(r["success"], r)
        self.assertEqual(r["total_count"], 3)
        self.assertEqual(r["totals_by_currency"], {"EUR": 350.5, "USD": 40})
        self.assertEqual(r["buckets"]["1-30"]["EUR"], {"count": 1, "amount": 100})
        self.assertEqual(r["buckets"]["61-90"]["EUR"]["count"], 1)
        self.assertEqual(r["buckets"]["90+"]["USD"]["amount"], 40)
        self.assertEqual(r["buckets"]["31-60"], {})
        self.assertEqual(r["parties"][0]["party"], "acme")
        self.assertEqual((r["parties"][0]["invoices"], r["parties"][0]["oldest_days"]), (2, 61))
        self.assertEqual(r["invoices"][0]["days_overdue"], 6)

    def test_filters_sent_to_get_list(self):
        self._run([], party="ZZ-C", company="ZZ Co", min_days_overdue=10)
        kwargs = self.get_list_call.kwargs
        self.assertEqual(self.get_list_call.args[0], "Sales Invoice")
        f = kwargs["filters"]
        self.assertEqual((f["docstatus"], f["is_return"], f["customer"], f["company"]), (1, 0, "ZZ-C", "ZZ Co"))
        self.assertEqual(f["due_date"], ["<=", "2026-09-21"])
        self.assertFalse(kwargs["ignore_permissions"])

    def test_supplier_reads_purchase_invoices(self):
        self._run([], party_type="Supplier")
        self.assertEqual(self.get_list_call.args[0], "Purchase Invoice")
        self.assertIn("supplier as party", self.get_list_call.kwargs["fields"])

    def test_limit_and_truncation(self):
        rows = [_row(f"SINV-{i}", "acme", "2026-09-01", 1) for i in range(1001)]
        r = self._run(rows, limit=5)
        self.assertTrue(r["truncated"])
        self.assertEqual(r["total_count"], 1000)
        self.assertEqual(len(r["invoices"]), 5)

    def test_bad_arguments(self):
        self.assertFalse(self._run(party_type="Employee")["success"])
        self.assertFalse(self._run(as_of="nonsense")["success"])

    def test_real_site_returns_structure(self):
        r = self._run()
        self.assertTrue(r["success"], r)
        self.assertEqual(set(r["buckets"]), {"1-30", "31-60", "61-90", "90+"})
        self.assertIsInstance(r["invoices"], list)

    def test_denied_without_read_permission(self):
        email = "zz-od-t3@example.com"
        user = frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": "ZZ Od", "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
        try:
            frappe.set_user(email)
            with self.enforce_only_for_checks():
                r = self._run()
            self.assertFalse(r["success"], r)
        finally:
            frappe.set_user("Administrator")
            frappe.delete_doc("User", user.name, force=True, ignore_permissions=True)
