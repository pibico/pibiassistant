"""A tool that fails after writing must not leave partial writes behind."""

import frappe

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.tests.base_test import BaseAssistantTest


def _make_tool(todo_name, exc):
    class ZZRollbackTool(BaseTool):
        def __init__(self):
            super().__init__()
            self.name = "zz_rollback_tool"
            self.inputSchema = {"type": "object", "properties": {}}

        def execute(self, arguments):
            frappe.db.set_value("ToDo", todo_name, "description", "ZZ changed")
            if exc is None:
                return {"success": False, "error": "reported"}
            raise exc

    return ZZRollbackTool()


class TestBaseToolRollback(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ZZ original"}).insert(
            ignore_permissions=True
        )

    def tearDown(self):
        frappe.delete_doc("ToDo", self.todo.name, force=True, ignore_permissions=True)
        super().tearDown()

    def _check(self, exc, error_type):
        before = frappe.db.count("PA Audit Log", {"tool_name": "zz_rollback_tool"})
        result = _make_tool(self.todo.name, exc)._safe_execute({})
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], error_type)
        self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "description"), "ZZ original")
        self.assertEqual(frappe.db.count("PA Audit Log", {"tool_name": "zz_rollback_tool"}), before + 1)

    def test_validation_error_rolls_back(self):
        self._check(frappe.ValidationError("bad"), "ValidationError")

    def test_permission_error_rolls_back(self):
        self._check(frappe.PermissionError("no"), "PermissionError")

    def test_generic_error_rolls_back(self):
        self._check(ValueError("boom"), "ExecutionError")

    def test_reported_failure_rolls_back(self):
        self._check(None, "ToolReportedError")

    def test_success_keeps_write(self):
        class Ok(BaseTool):
            def __init__(s):
                super().__init__()
                s.name = "zz_rollback_tool"
                s.inputSchema = {"type": "object", "properties": {}}

            def execute(s, arguments):
                frappe.db.set_value("ToDo", self_todo, "description", "ZZ kept")
                return {"ok": 1}

        self_todo = self.todo.name
        self.assertTrue(Ok()._safe_execute({})["success"])
        self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "description"), "ZZ kept")
