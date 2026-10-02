import frappe

from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.utils import cache


class TestServerSettingsCache(BaseAssistantTest):
    def test_settings_payload(self):
        data = cache.get_cached_server_settings()
        self.assertTrue(data["mcp_endpoint_url"].endswith("handle_mcp"))
        self.assertIn("oauth_discovery_url", data)

    def test_invalidate_actually_clears_the_cached_function(self):
        cache.get_cached_server_settings()
        key = "pibiassistant.utils.cache.get_cached_server_settings"
        self.assertTrue(frappe.cache.get_keys(key))
        cache.invalidate_settings_cache()
        self.assertFalse(frappe.cache.get_keys(key))

    def test_dead_dashboard_layer_is_gone(self):
        import importlib

        with self.assertRaises(ImportError):
            importlib.import_module("pibiassistant.utils.dashboard")
        from pibiassistant import hooks

        self.assertNotIn("warm_cache", str(hooks.scheduler_events))
        self.assertNotIn("invalidate_dashboard_cache", str(hooks.doc_events))
        self.assertFalse(hasattr(hooks, "app_startup"))
        self.assertFalse(hasattr(hooks, "jenv"))
