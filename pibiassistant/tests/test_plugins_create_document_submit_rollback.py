"""A failed submit must roll back its own writes so the draft message stays true."""

from unittest.mock import patch

import frappe

from pibiassistant.plugins.core.tools.create_document import DocumentCreate
from pibiassistant.plugins.core.tools.submit_document import DocumentSubmit
from pibiassistant.tests.base_test import BaseAssistantTest


def _leaky_submit(self, *args, **kwargs):
    frappe.db.set_value("ToDo", self.name, "description", "ZZ leaked by submit")
    raise frappe.ValidationError("ZZ insufficient stock")


class TestSubmitRollback(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.meta = frappe.get_meta("ToDo")
        self._was_submittable = self.meta.is_submittable
        self.meta.is_submittable = 1
        self.addCleanup(setattr, self.meta, "is_submittable", self._was_submittable)

    def test_create_document_submit_failure_keeps_clean_draft(self):
        with patch("frappe.model.document.Document.submit", _leaky_submit):
            result = DocumentCreate().execute(
                {"doctype": "ToDo", "data": {"description": "ZZ draft kept"}, "submit": True}
            )
        self.assertTrue(result["success"], result)
        self.assertFalse(result["submitted"])
        self.assertIn("draft", result["message"])
        row = frappe.db.get_value("ToDo", result["name"], ["docstatus", "description"], as_dict=True)
        self.assertEqual(row.docstatus, 0)
        self.assertEqual(row.description, "ZZ draft kept")

    def test_submit_document_failure_rolls_back_partial_writes(self):
        todo = frappe.get_doc({"doctype": "ToDo", "description": "ZZ submit me"}).insert()
        with patch("frappe.model.document.Document.submit", _leaky_submit):
            result = DocumentSubmit().execute({"doctype": "ToDo", "name": todo.name})
        self.assertFalse(result["success"])
        row = frappe.db.get_value("ToDo", todo.name, ["docstatus", "description"], as_dict=True)
        self.assertEqual(row.docstatus, 0)
        self.assertEqual(row.description, "ZZ submit me")
