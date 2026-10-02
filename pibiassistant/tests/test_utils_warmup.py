from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.utils import warmup


class TestToolRegistryWarmup(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        warmup._warmed = False
        self.addCleanup(setattr, warmup, "_warmed", False)

    def _run(self, path):
        request = MagicMock(path=path)
        with patch.object(frappe.local, "request", request, create=True), \
             patch("pibiassistant.utils.plugin_manager.get_plugin_manager") as pm:
            warmup.prewarm_tool_registry()
            warmup.prewarm_tool_registry()
            return pm

    def test_warms_once_on_chat_page(self):
        pm = self._run("/aida/chat")
        self.assertEqual(pm.return_value.get_all_tools.call_count, 1)

    def test_ignores_unrelated_paths(self):
        pm = self._run("/api/method/ping")
        pm.return_value.get_all_tools.assert_not_called()
        self.assertFalse(warmup._warmed)

    def test_failure_does_not_break_request(self):
        request = MagicMock(path="/app")
        with patch.object(frappe.local, "request", request, create=True), \
             patch("pibiassistant.utils.plugin_manager.get_plugin_manager", side_effect=RuntimeError("x")):
            warmup.prewarm_tool_registry()
