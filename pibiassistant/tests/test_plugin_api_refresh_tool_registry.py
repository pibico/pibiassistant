import frappe

from pibiassistant.api import plugin_api
from pibiassistant.tests.base_test import BaseAssistantTest


class TestRefreshToolRegistry(BaseAssistantTest):
    def test_refresh_returns_stats_without_error_log(self):
        frappe.set_user("Administrator")
        before = frappe.db.count("Error Log", {"method": ["like", "%Tool Registry Refresh%"]})
        result = plugin_api.refresh_tool_registry()
        self.assertTrue(result["success"])
        self.assertIn("stats", result)
        after = frappe.db.count("Error Log", {"method": ["like", "%Tool Registry Refresh%"]})
        self.assertEqual(before, after)
