# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""create/update/list/report tools: field guards, limits and non-empty permission errors."""

from unittest.mock import patch

import frappe

from pibiassistant.plugins.core.tools.create_document import DocumentCreate
from pibiassistant.plugins.core.tools.list_documents import DocumentList
from pibiassistant.plugins.core.tools.report_tools import ReportTools
from pibiassistant.plugins.core.tools.update_document import DocumentUpdate
from pibiassistant.tests.base_test import BaseAssistantTest


class TestListDocumentsLimit(BaseAssistantTest):
    def _limit_seen(self, limit):
        with patch("frappe.get_list", return_value=[]) as get_list:
            result = DocumentList().execute({"doctype": "ToDo", "limit": limit})
        self.assertTrue(result["success"], result)
        return get_list.call_args_list[0].kwargs["limit"]

    def test_limit_is_clamped(self):
        self.assertEqual(self._limit_seen(1_000_000), 1000)
        self.assertEqual(self._limit_seen(0), 20)
        self.assertEqual(self._limit_seen(-1), 20)
        self.assertEqual(self._limit_seen(5), 5)


class TestFieldGuards(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ZZ guard o3"}).insert(
            ignore_permissions=True
        )

    def tearDown(self):
        frappe.delete_doc("ToDo", self.todo.name, force=True, ignore_permissions=True)
        super().tearDown()

    def _update(self, data):
        return DocumentUpdate().execute({"doctype": "ToDo", "name": self.todo.name, "data": data})

    def test_update_rejects_docstatus(self):
        result = self._update({"docstatus": 1})
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "system_field")
        self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "docstatus"), 0)

    def test_update_rejects_unknown_field(self):
        result = self._update({"nonexistent_field": "x"})
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "unknown_field")

    def test_update_valid_field_still_works(self):
        result = self._update({"description": "ZZ guard o3 changed"})
        self.assertTrue(result["success"], result)
        self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "description"), "ZZ guard o3 changed")

    def test_create_rejects_docstatus_and_unknown_fields(self):
        for data, kind in (({"description": "ZZ x", "docstatus": 1}, "system_field"), ({"bogus": 1}, "unknown_field")):
            for validate_only in (False, True):
                result = DocumentCreate().execute(
                    {"doctype": "ToDo", "data": data, "validate_only": validate_only}
                )
                self.assertFalse(result["success"], result)
                self.assertEqual(result["error_type"], kind)

    def test_create_submit_ignored_for_non_submittable(self):
        result = DocumentCreate().execute(
            {"doctype": "ToDo", "data": {"description": "ZZ submit o3"}, "submit": True}
        )
        try:
            self.assertTrue(result["success"], result)
            self.assertEqual(result["docstatus"], 0)
            self.assertIn("not submittable", result["message"])
        finally:
            if result.get("name"):
                frappe.delete_doc("ToDo", result["name"], force=True, ignore_permissions=True)


class TestPermissionErrorsAreNotEmpty(BaseAssistantTest):
    def test_create_permission_error_has_message(self):
        with patch("frappe.new_doc", side_effect=frappe.PermissionError()):
            result = DocumentCreate().execute({"doctype": "ToDo", "data": {"description": "ZZ"}})
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "permission_error")
        self.assertTrue(result["error"])

    def test_update_permission_error_has_message(self):
        todo = frappe.get_doc({"doctype": "ToDo", "description": "ZZ perm o3"}).insert(ignore_permissions=True)
        try:
            with patch("frappe.get_doc", side_effect=frappe.PermissionError()):
                result = DocumentUpdate().execute(
                    {"doctype": "ToDo", "name": todo.name, "data": {"description": "ZZ y"}}
                )
            self.assertEqual(result["error_type"], "permission_error")
            self.assertTrue(result["error"])
        finally:
            frappe.delete_doc("ToDo", todo.name, force=True, ignore_permissions=True)


class TestReportErrorsSurface(BaseAssistantTest):
    def test_failing_script_report_is_not_success(self):
        failing = {"result": [], "columns": [], "message": "Script report execution failed: boom", "error": "boom"}
        with patch.object(ReportTools, "_execute_script_report", return_value=failing):
            result = ReportTools.execute_report("General Ledger", {})
        self.assertFalse(result["success"], result)
        self.assertEqual(result["error"], "boom")
