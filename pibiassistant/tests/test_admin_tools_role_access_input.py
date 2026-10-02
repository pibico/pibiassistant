import frappe

from pibiassistant.api.admin import tools as admin_tools
from pibiassistant.tests.base_test import BaseAssistantTest


class TestAdminToolsRoleAccessInput(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def test_role_access_rejects_malformed_json(self):
        result = admin_tools.update_tool_role_access("list_documents", "Restrict to Listed Roles", "{bad")
        self.assertFalse(result["success"])

    def test_restrict_mode_requires_roles(self):
        for roles in ([], "[]", None):
            result = admin_tools.update_tool_role_access("list_documents", "Restrict to Listed Roles", roles)
            self.assertFalse(result["success"], roles)

    def test_bulk_toggle_rejects_malformed_json(self):
        result = admin_tools.bulk_toggle_tools("not json", True)
        self.assertFalse(result["success"])
        self.assertEqual(result["toggled"], [])

    def test_bulk_toggle_rejects_non_list(self):
        self.assertFalse(admin_tools.bulk_toggle_tools('{"a": 1}', True)["success"])
