import frappe

from pibiassistant.core.tool_registry import get_role_access_by_parent, get_tool_registry
from pibiassistant.tests.base_test import BaseAssistantTest


class TestToolConfigCache(BaseAssistantTest):
    def _queries(self, fn):
        counter = {"n": 0}
        original = frappe.db.sql

        def spy(*args, **kwargs):
            counter["n"] += 1
            return original(*args, **kwargs)

        frappe.db.sql = spy
        try:
            fn()
        finally:
            del frappe.db.sql
        return counter["n"]

    def test_cache_miss_does_not_poison_later_reads(self):
        registry = get_tool_registry()
        registry.clear_cache()
        registry._get_tool_configurations()  # miss, populates redis
        n = self._queries(lambda: [registry._get_tool_configurations() for _ in range(50)])
        self.assertEqual(n, 0)

    def test_registry_build_is_cheap_after_cache_clear(self):
        from pibiassistant.api.pa_endpoint import _build_tool_registry

        frappe.set_user("Administrator")
        frappe.clear_cache()
        _build_tool_registry()
        self.assertLessEqual(self._queries(_build_tool_registry), 8)

    def test_role_access_is_grouped_in_one_query(self):
        names = frappe.get_all("PA Tool Configuration", pluck="name")
        self.assertEqual(self._queries(lambda: get_role_access_by_parent(names)), 1)
        self.assertEqual(get_role_access_by_parent([]), {})
