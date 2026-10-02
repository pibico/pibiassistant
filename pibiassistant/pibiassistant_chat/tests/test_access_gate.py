# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for the can_use_pao access gate (AIDA runs natively: role based, no cloud seats)."""

from unittest.mock import patch

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest

ACCESS = "pibiassistant.pibiassistant_chat.api.settings.access"


class TestAccessGate(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _can_use(self, aida=True, chat=True):
        from pibiassistant.pibiassistant_chat.api.settings.access import can_use_pao

        with patch(f"{ACCESS}.is_chat_enabled", return_value=chat), patch(f"{ACCESS}._aida_mode", return_value=aida):
            return can_use_pao()

    def test_chat_module_disabled_reports_diagnostics_false(self):
        """enable_pa_chat off hides the widget and reports diagnostics disabled outright."""
        result = self._can_use(chat=False)
        self.assertFalse(result.get("show_widget"))
        self.assertEqual(result.get("status"), "chat_module_disabled")
        self.assertIs(result.get("enable_browser_diagnostics"), False, f"got {result}")

    def test_aida_admin_can_use(self):
        result = self._can_use()
        self.assertTrue(result.get("can_use"))
        self.assertEqual(result.get("status"), "ready")
        self.assertTrue(result.get("is_admin"))

    def test_aida_guest_is_not_logged_in(self):
        frappe.set_user("Guest")
        result = self._can_use()
        self.assertFalse(result.get("can_use"))
        self.assertEqual(result.get("status"), "not_logged_in")

    def test_without_aida_key_the_widget_gets_the_onboarding_status(self):
        result = self._can_use(aida=False)
        self.assertFalse(result.get("can_use"))
        self.assertEqual(result.get("status"), "not_registered")
        self.assertIn("enable_browser_diagnostics", result)

    def test_exception_branch_omits_the_diagnostics_key_entirely(self):
        """An internal error must not return enable_browser_diagnostics: its ABSENCE tells
        widget.js the value is an inferred fail-open default, not a real answer to persist."""
        from pibiassistant.pibiassistant_chat.api.settings.access import can_use_pao

        with patch(f"{ACCESS}.is_chat_enabled", return_value=True), patch(
            f"{ACCESS}._aida_mode", return_value=False
        ), patch(f"{ACCESS}.frappe.get_single", side_effect=RuntimeError("boom")):
            result = can_use_pao()

        self.assertEqual(result.get("status"), "error")
        self.assertNotIn("enable_browser_diagnostics", result, f"got {result}")
