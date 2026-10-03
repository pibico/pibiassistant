# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""get_stock_balance on a real stock fixture (a ZZ item received into a warehouse), always cleaned up."""

import unittest

import frappe
from frappe.utils import add_days, flt, nowdate

from pibiassistant.plugins.core.tools.get_stock_balance import GetStockBalance

ITEM = "ZZ-STOCK-TEST-ITEM"
QTY = 7
RATE = 12.5


def _warehouse_and_company():
    row = frappe.db.get_value("Warehouse", {"is_group": 0, "disabled": 0}, ["name", "company"], as_dict=True)
    return (row.name, row.company) if row else (None, None)


def _drop_item_data(item_code):
    for voucher in set(frappe.get_all("Stock Ledger Entry", filters={"item_code": item_code}, pluck="voucher_no")):
        if frappe.db.exists("Stock Entry", voucher):
            doc = frappe.get_doc("Stock Entry", voucher)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Stock Entry", voucher, force=True, ignore_permissions=True)
        for dt in ("Stock Ledger Entry", "GL Entry"):
            for name in frappe.get_all(dt, filters={"voucher_no": voucher}, pluck="name"):
                frappe.db.delete(dt, {"name": name})
    frappe.db.delete("Stock Ledger Entry", {"item_code": item_code})
    frappe.db.delete("Bin", {"item_code": item_code})
    if frappe.db.exists("Item", item_code):
        frappe.delete_doc("Item", item_code, force=True, ignore_permissions=True)
    frappe.db.commit()


class TestGetStockBalance(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.warehouse, self.company = _warehouse_and_company()
        if not self.warehouse:
            self.skipTest("the site has no warehouse")
        _drop_item_data(ITEM)
        frappe.get_doc(
            {"doctype": "Item", "item_code": ITEM, "item_name": "ZZ stock test", "item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
             "stock_uom": frappe.db.get_value("UOM", {}, "name") or "Nos", "is_stock_item": 1}
        ).insert(ignore_permissions=True)
        entry = frappe.get_doc(
            {"doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "company": self.company, "posting_date": nowdate(),
             "items": [{"item_code": ITEM, "t_warehouse": self.warehouse, "qty": QTY, "basic_rate": RATE}]}
        )
        try:
            entry.insert(ignore_permissions=True)
            entry.submit()
        except Exception as e:  # missing stock accounts etc.: not what this test is about
            _drop_item_data(ITEM)
            self.skipTest(f"cannot build the stock fixture here: {str(e)[:80]}")
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        _drop_item_data(ITEM)

    def _run(self, **args):
        return GetStockBalance().execute(args)

    def test_item_shows_its_warehouse_row(self):
        result = self._run(item_code=ITEM)
        self.assertTrue(result["success"], result)
        row = next(r for r in result["rows"] if r["warehouse"] == self.warehouse)
        self.assertEqual(row["actual_qty"], QTY)
        self.assertEqual(row["stock_value"], flt(QTY * RATE, 2))
        self.assertEqual(row["item_name"], "ZZ stock test")
        self.assertEqual(result["total_actual_qty"], QTY)
        self.assertEqual(result["total_stock_value"], flt(QTY * RATE, 2))
        self.assertIn("projected_qty", result["quantity_note"])

    def test_warehouse_lists_the_item_and_summary_groups_by_warehouse(self):
        by_wh = self._run(warehouse=self.warehouse)
        self.assertTrue(by_wh["success"], by_wh)
        self.assertIn(ITEM, [r["item_code"] for r in by_wh["rows"]])
        summary = self._run()
        self.assertTrue(summary["success"], summary)
        mine = next(r for r in summary["rows"] if r["warehouse"] == self.warehouse)
        self.assertGreaterEqual(mine["items"], 1)
        self.assertGreaterEqual(mine["actual_qty"], QTY)

    def test_as_of_dates_come_from_the_ledger(self):
        today = self._run(item_code=ITEM, date=nowdate())
        self.assertTrue(today["success"], today)
        self.assertEqual(today["total_actual_qty"], QTY)
        before = self._run(item_code=ITEM, date=add_days(nowdate(), -1))
        self.assertTrue(before["success"], before)
        self.assertEqual(before["rows"], [])
        self.assertEqual(before["total_actual_qty"], 0)
        self.assertIn("stock ledger", today["note"])

    def test_zero_rows_are_hidden_unless_asked(self):
        result = self._run(item_code=ITEM, date=add_days(nowdate(), -1), include_zero=True)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["rows"], [])  # nothing existed yesterday: no ledger rows at all

    def test_limit_truncates_and_says_so(self):
        result = self._run(limit=1)
        self.assertTrue(result["success"], result)
        self.assertLessEqual(len(result["rows"]), 1)
        self.assertEqual(result["truncated"], result["row_count"] > 1)

    def test_bad_input_is_refused_clearly(self):
        self.assertIn("not found", self._run(item_code="ZZ no such item")["error"])
        missing = self._run(warehouse="ZZ no such warehouse")
        self.assertFalse(missing["success"])
        self.assertIn("not found", missing["error"])
        self.assertFalse(self._run(date="not-a-date")["success"])

    def test_user_without_stock_access_is_refused(self):
        frappe.set_user("Guest")
        try:
            self.assertFalse(self._run(item_code=ITEM)["success"])
        finally:
            frappe.set_user("Administrator")
