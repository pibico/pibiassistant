from unittest.mock import patch

from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.utils import migration_hooks

SYNC_HELPERS = (
    "_install_system_prompt_categories",
    "_install_system_prompt_templates",
    "_install_system_skills",
    "_install_app_skills",
    "_sync_plugin_configurations",
    "_sync_tool_configurations",
    "_set_settings_defaults",
)


class TestAfterInstall(BaseAssistantTest):
    def test_tool_discovery_is_initialised_through_tool_cache(self):
        patches = [patch.object(migration_hooks, name) for name in SYNC_HELPERS]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        with patch("pibiassistant.utils.tool_cache.refresh_tool_cache", return_value={"success": True, "stats": {"available_tools": 3}}) as refresh, patch(
            "frappe.logger"
        ) as logger:
            migration_hooks.after_install()
        refresh.assert_called_once_with(force=True)
        errors = [c for c in logger.return_value.error.call_args_list]
        self.assertEqual(errors, [])

    def test_migration_status_uses_existing_registry_api(self):
        status = migration_hooks.get_migration_status()
        self.assertNotIn("error", status, status)
        self.assertTrue(status["migration_hooks_active"])
