"""cancel_document, amend_document, create_from_document, assign_document and add_comment on real documents."""

import unittest

import frappe
from frappe.utils import add_days, nowdate

from pibiassistant.plugins.core.tools.add_comment import DocumentComment
from pibiassistant.plugins.core.tools.amend_document import DocumentAmend
from pibiassistant.plugins.core.tools.assign_document import DocumentAssign
from pibiassistant.plugins.core.tools.cancel_document import DocumentCancel
from pibiassistant.plugins.core.tools.create_from_document import PAIRS, DocumentCreateFrom
from pibiassistant.pibiassistant_chat.api.chat.aida_tools import WRITE_TOOLS, _approval_card


def _make_quotation():
    customer = frappe.db.get_value("Customer", {}, "name")
    item = frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1}, "name")
    company = frappe.db.get_value("Company", {}, "name")
    if not (customer and item and company):
        return None
    doc = frappe.get_doc(
        {
            "doctype": "Quotation", "quotation_to": "Customer", "party_name": customer, "company": company,
            "transaction_date": nowdate(), "valid_till": add_days(nowdate(), 10), "order_type": "Sales",
            "items": [{"item_code": item, "qty": 1, "rate": 100}],
        }
    ).insert(ignore_permissions=True)
    doc.submit()
    frappe.db.commit()
    return doc.name


class TestLifecycleTools(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.quotation = _make_quotation()
        if not self.quotation:
            self.skipTest("the site has no customer, item and company to build a quotation")
        self.created = {"Quotation": [self.quotation], "Sales Order": []}

    def tearDown(self):
        frappe.set_user("Administrator")
        for dt in ("Sales Order", "Quotation"):
            for name in self.created.get(dt, []) + frappe.get_all(dt, filters={"amended_from": ["in", self.created.get(dt, [])]}, pluck="name"):
                if not frappe.db.exists(dt, name):
                    continue
                for todo in frappe.get_all("ToDo", filters={"reference_type": dt, "reference_name": name}, pluck="name"):
                    frappe.delete_doc("ToDo", todo, force=True, ignore_permissions=True)
                for comment in frappe.get_all("Comment", filters={"reference_doctype": dt, "reference_name": name}, pluck="name"):
                    frappe.delete_doc("Comment", comment, force=True, ignore_permissions=True)
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        frappe.db.commit()

    def test_create_sales_order_from_quotation_is_a_draft(self):
        result = DocumentCreateFrom().execute(
            {"source_doctype": "Quotation", "source_name": self.quotation, "target_doctype": "Sales Order", "delivery_date": add_days(nowdate(), 7)}
        )
        if result.get("success"):
            self.created["Sales Order"].append(result["name"])
        self.assertTrue(result["success"], result)
        self.assertEqual(result["docstatus"], 0)
        self.assertEqual(frappe.db.get_value("Sales Order Item", {"parent": result["name"]}, "prevdoc_docname"), self.quotation)

    def test_sales_order_without_delivery_date_asks_for_it(self):
        result = DocumentCreateFrom().execute({"source_doctype": "Quotation", "source_name": self.quotation, "target_doctype": "Sales Order"})
        self.assertFalse(result["success"])
        self.assertEqual(result.get("needs"), "delivery_date")
        self.assertFalse(frappe.db.exists("Sales Order Item", {"prevdoc_docname": self.quotation}))

    def test_create_from_refuses_unsupported_pairs_and_missing_sources(self):
        refused = DocumentCreateFrom().execute({"source_doctype": "Quotation", "source_name": self.quotation, "target_doctype": "Delivery Note"})
        self.assertFalse(refused["success"])
        self.assertIn("Sales Order", refused["error"])
        self.assertFalse(DocumentCreateFrom().execute({"source_doctype": "Quotation", "source_name": "ZZ-none", "target_doctype": "Sales Order"})["success"])
        self.assertFalse(DocumentCreateFrom().execute({"source_doctype": "User", "source_name": "Administrator", "target_doctype": "Role"})["success"])

    def test_every_supported_pair_points_at_a_real_method(self):
        for pair, (method, _style) in PAIRS.items():
            self.assertTrue(callable(frappe.get_attr(method)), pair)

    def test_cancel_then_amend(self):
        cancelled = DocumentCancel().execute({"doctype": "Quotation", "name": self.quotation})
        self.assertTrue(cancelled["success"], cancelled)
        self.assertEqual(frappe.db.get_value("Quotation", self.quotation, "docstatus"), 2)
        self.assertFalse(DocumentCancel().execute({"doctype": "Quotation", "name": self.quotation})["success"])

        amended = DocumentAmend().execute({"doctype": "Quotation", "name": self.quotation})
        self.assertTrue(amended["success"], amended)
        self.assertEqual(amended["docstatus"], 0)
        self.assertEqual(frappe.db.get_value("Quotation", amended["name"], "amended_from"), self.quotation)
        self.assertTrue(amended["name"].startswith(self.quotation))
        again = DocumentAmend().execute({"doctype": "Quotation", "name": self.quotation})
        self.assertFalse(again["success"])
        self.assertIn("already amended", again["error"])

    def test_amend_and_cancel_refuse_wrong_states(self):
        self.assertIn("not cancelled", DocumentAmend().execute({"doctype": "Quotation", "name": self.quotation})["error"])
        self.assertIn("not submittable", DocumentCancel().execute({"doctype": "ToDo", "name": "x"})["error"])

    def test_cancel_is_blocked_while_a_submitted_document_depends_on_it(self):
        so = DocumentCreateFrom().execute({"source_doctype": "Quotation", "source_name": self.quotation, "target_doctype": "Sales Order", "delivery_date": add_days(nowdate(), 7)})
        self.assertTrue(so["success"], so)
        self.created["Sales Order"].append(so["name"])
        order = frappe.get_doc("Sales Order", so["name"])
        order.submit()
        frappe.db.commit()
        blocked = DocumentCancel().execute({"doctype": "Quotation", "name": self.quotation})
        self.assertFalse(blocked["success"], blocked)
        self.assertIn(so["name"], blocked["error"])
        self.assertEqual(frappe.db.get_value("Quotation", self.quotation, "docstatus"), 1)

    def test_assign_and_unassign(self):
        user = frappe.db.get_value("User", {"enabled": 1, "name": ["not in", ["Administrator", "Guest"]], "user_type": "System User"}, "name")
        self.assertTrue(user)
        added = DocumentAssign().execute({"doctype": "Quotation", "name": self.quotation, "assign_to": [user], "description": "ZZ test"})
        self.assertTrue(added["success"], added)
        self.assertIn(user, added["assigned_now"])
        removed = DocumentAssign().execute({"doctype": "Quotation", "name": self.quotation, "assign_to": [user], "action": "remove"})
        self.assertTrue(removed["success"], removed)
        self.assertNotIn(user, removed["assigned_now"])

    def test_assign_refuses_unknown_and_disabled_users(self):
        self.assertIn("not found", DocumentAssign().execute({"doctype": "Quotation", "name": self.quotation, "assign_to": ["nobody@example.invalid"]})["error"])
        self.assertFalse(DocumentAssign().execute({"doctype": "Quotation", "name": self.quotation, "assign_to": []})["success"])
        self.assertFalse(DocumentAssign().execute({"doctype": "Quotation", "name": self.quotation, "assign_to": ["Guest"]})["success"])

    def test_comment(self):
        result = DocumentComment().execute({"doctype": "Quotation", "name": self.quotation, "comment": "Nota <b>de</b> prueba\nsegunda línea"})
        self.assertTrue(result["success"], result)
        row = frappe.db.get_value("Comment", result["comment_id"], ["content", "comment_email", "comment_type"], as_dict=True)
        self.assertEqual(row.comment_type, "Comment")
        self.assertNotIn("<b>", row.content)
        self.assertIn("<br>", row.content)
        self.assertFalse(DocumentComment().execute({"doctype": "Quotation", "name": self.quotation, "comment": "   "})["success"])
        self.assertFalse(DocumentComment().execute({"doctype": "Quotation", "name": self.quotation, "comment": "x" * 6000})["success"])

    def test_guest_cannot_use_any_of_them(self):
        frappe.set_user("Guest")
        try:
            for tool, args in (
                (DocumentCancel(), {"doctype": "Quotation", "name": self.quotation}),
                (DocumentComment(), {"doctype": "Quotation", "name": self.quotation, "comment": "hola"}),
                (DocumentCreateFrom(), {"source_doctype": "Quotation", "source_name": self.quotation, "target_doctype": "Sales Order"}),
            ):
                self.assertFalse(tool.execute(args)["success"], tool.name)
        finally:
            frappe.set_user("Administrator")

    def test_chat_treats_them_as_writes_with_a_card_preview(self):
        for tool in ("cancel_document", "amend_document", "create_from_document", "assign_document", "add_comment"):
            self.assertIn(tool, WRITE_TOOLS)
        card = _approval_card(
            {"interrupt_id": "i1", "name": "create_from_document",
             "arguments": {"source_doctype": "Quotation", "source_name": self.quotation, "target_doctype": "Sales Order"}}
        )
        self.assertIn("draft Sales Order", card["reason"]["description"])
        card = _approval_card({"interrupt_id": "i2", "name": "cancel_document", "arguments": {"doctype": "Quotation", "name": self.quotation}})
        self.assertIn("Cancel Quotation", card["reason"]["description"])
