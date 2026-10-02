import frappe

from pibiassistant.core.security_config import validate_document_access
from pibiassistant.tests.base_test import BaseAssistantTest


class TestMissingDocumentAccess(BaseAssistantTest):
    def test_missing_doc_reports_not_found_without_error_log(self):
        before = frappe.db.count("Error Log")
        result = validate_document_access("zz-nobody@example.com", "ToDo", "zz-nope-missing", "read")
        self.assertFalse(result["success"])
        self.assertIn("zz-nope-missing", result["error"])
        self.assertRegex(result["error"], "not found|no encontrado")
        self.assertNotIn("Permission validation failed", result["error"])
        self.assertEqual(frappe.db.count("Error Log"), before)


class TestMissingDocTypeAccess(BaseAssistantTest):
    def test_unknown_doctype_reports_not_found_without_error_log(self):
        before = frappe.db.count("Error Log")
        for perm in ("read", "write", "create", "delete"):
            result = validate_document_access("zz-nobody@example.com", "ZZNoSuchDocType", "x", perm)
            self.assertFalse(result["success"])
            self.assertIn("ZZNoSuchDocType", result["error"])
            self.assertRegex(result["error"], "not found|no encontrado")
            self.assertNotIn("Permission validation failed", result["error"])
        self.assertEqual(frappe.db.count("Error Log"), before)

    def test_five_core_tools_report_unknown_doctype_cleanly(self):
        from pibiassistant.core.tool_registry import get_tool_registry

        frappe.set_user("zz-nobody@example.com")
        self.addCleanup(frappe.set_user, "Administrator")
        registry = get_tool_registry()
        before = frappe.db.count("Error Log")
        calls = {
            "get_document": {"doctype": "ZZNoSuchDocType", "name": "x"},
            "list_documents": {"doctype": "ZZNoSuchDocType"},
            "create_document": {"doctype": "ZZNoSuchDocType", "data": {"a": 1}},
            "update_document": {"doctype": "ZZNoSuchDocType", "name": "x", "data": {"a": 1}},
            "delete_document": {"doctype": "ZZNoSuchDocType", "name": "x"},
        }
        for tool, args in calls.items():
            tool_instance = registry.get_tool(tool)
            self.assertIsNotNone(tool_instance, tool)
            try:
                result = tool_instance.execute(args)
            except Exception as e:  # tools may raise instead of returning
                result = {"error": str(e)}
            text = str(result)
            self.assertNotIn("Permission validation failed", text, tool)
        self.assertEqual(frappe.db.count("Error Log"), before)
