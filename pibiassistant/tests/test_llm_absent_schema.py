"""Every new reader and endpoint behaves as today when the PA LLM Provider table and the new fields are absent."""

from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.pibiassistant_chat.api import aida, llm_admin, models
from pibiassistant.pibiassistant_chat.api.chat import aida_tools
from pibiassistant.tests.base_test import BaseAssistantTest


class TestAbsentSchema(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        settings = MagicMock()
        settings.get.return_value = None
        self._patches = [
            patch("frappe.db.table_exists", return_value=False),
            patch("pibiassistant.pibiassistant_chat.api.llm_config._settings", return_value=settings),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        super().tearDown()

    def test_endpoints_do_not_raise(self):
        with patch("pibiassistant.pibiassistant_chat.aida_mode.is_aida_mode", return_value=False):
            models.get_available_models()
        with patch("pibiassistant.pibiassistant_chat.aida_mode.is_aida_mode", return_value=True):
            aida.get_overview()
            aida.cached_connection_status()
        status = aida_tools.aida_status(frappe.session.user)
        self.assertNotIn("direct_providers", status)

    def test_admin_endpoints_fail_with_a_clear_message(self):
        frappe.set_user("Administrator")
        with self.assertRaises(frappe.ValidationError):
            llm_admin.test_provider("zz-row")
        catalog = llm_admin.get_provider_catalog()
        self.assertIn("providers", catalog)
