from unittest.mock import patch

import frappe

from pibiassistant.api.admin import tools as admin_tools
from pibiassistant.tests.base_test import BaseAssistantTest


class TestAdminToolsQueries(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _count(self, fn):
        counter = {"n": 0}
        original = frappe.db.sql

        def spy(*args, **kwargs):
            counter["n"] += 1
            return original(*args, **kwargs)

        frappe.db.sql = spy
        try:
            return fn(), counter["n"]
        finally:
            del frappe.db.sql

    def test_list_has_no_per_tool_role_queries(self):
        admin_tools.get_tool_configurations()  # warm imports
        result, queries = self._count(admin_tools.get_tool_configurations)
        self.assertTrue(result.get("success", True))
        self.assertLessEqual(queries, 12, f"{queries} queries")

    def test_unconfigured_tools_get_detected_category(self):
        result = admin_tools.get_tool_configurations()
        configured = set(frappe.get_all("PA Tool Configuration", pluck="tool_name"))
        unconfigured = [t for t in result["tools"] if t["name"] not in configured]
        for tool in unconfigured:
            self.assertIn(tool["category"], ("read_only", "write", "read_write", "privileged"), tool["name"])
        if unconfigured:
            self.assertTrue(any(t["category"] != "read_write" for t in unconfigured))

    def test_bulk_toggle_targets_tools_without_configuration_rows(self):
        configured = set(frappe.get_all("PA Tool Configuration", pluck="tool_name"))
        all_names = {t["name"] for t in admin_tools.get_tool_configurations()["tools"]}
        missing = all_names - configured
        if not missing:
            self.skipTest("every discovered tool already has a configuration row")
        seen = []
        with patch.object(admin_tools, "toggle_tool", side_effect=lambda n, e: seen.append(n) or {"success": True}):
            result = admin_tools.bulk_toggle_tools_by_category(enabled=False)
        self.assertTrue(missing <= set(seen), missing - set(seen))
        self.assertEqual(result["total"], len(seen))

    def test_bulk_toggle_filters_by_category_and_plugin(self):
        by_plugin = {}
        for tool in admin_tools.get_tool_configurations()["tools"]:
            by_plugin.setdefault(tool["plugin_name"], []).append(tool)
        plugin, tools = next(iter(by_plugin.items()))
        category = tools[0]["category"]
        expected = sorted(t["name"] for t in tools if t["category"] == category)
        seen = []
        with patch.object(admin_tools, "toggle_tool", side_effect=lambda n, e: seen.append(n) or {"success": True}):
            admin_tools.bulk_toggle_tools_by_category(category=category, enabled=True, plugin_name=plugin)
        self.assertEqual(sorted(seen), expected)
