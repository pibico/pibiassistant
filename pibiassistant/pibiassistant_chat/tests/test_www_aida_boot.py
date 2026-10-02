"""The /aida boot payload carries the site timezone and the access verdict."""

from unittest.mock import patch

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.www.aida import get_boot


class TestAidaBoot(BaseAssistantTest):
    def test_boot_exposes_site_timezone(self):
        tz = get_boot()["aida_tz"]
        self.assertIsInstance(tz, str)
        self.assertTrue(tz)
        self.assertEqual(tz, frappe.utils.get_system_timezone())

    def test_boot_can_use_follows_the_gate(self):
        gate = "pibiassistant.pibiassistant_chat.api.settings.access.can_use_pao"
        with patch(gate, return_value={"can_use": False}):
            self.assertIs(get_boot()["can_use"], False)
        with patch(gate, return_value={"can_use": True}):
            self.assertIs(get_boot()["can_use"], True)

    def test_boot_can_use_fails_open_when_the_gate_errors(self):
        gate = "pibiassistant.pibiassistant_chat.api.settings.access.can_use_pao"
        with patch(gate, side_effect=RuntimeError("boom")), patch("frappe.log_error"):
            self.assertIs(get_boot()["can_use"], True)
