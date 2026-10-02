"""One AIDA-mode check, tolerant of a never-saved key, shared by every caller."""

import unittest
from unittest.mock import patch

import frappe
import frappe.sessions  # noqa: F401

from pibiassistant.pibiassistant_chat.api import _helpers
from pibiassistant.pibiassistant_chat.api.chat import aida_stream
from pibiassistant.pibiassistant_chat.api.settings import access, capabilities

PW = "frappe.utils.password.get_decrypted_password"


class TestAidaModeHelper(unittest.TestCase):
    def test_aliases_point_to_one_function(self):
        self.assertIs(_helpers._aida_mode, _helpers.is_aida_mode)
        self.assertIs(aida_stream.is_aida_mode, _helpers.is_aida_mode)

    def test_key_set_and_unset(self):
        with patch(PW, return_value="secret"):
            self.assertTrue(_helpers.is_aida_mode())
        with patch(PW, return_value=None):
            self.assertFalse(_helpers.is_aida_mode())
        with patch(PW, side_effect=Exception("never saved")):
            self.assertFalse(_helpers.is_aida_mode())

    def test_callers_do_not_raise_without_a_key(self):
        with patch(PW, side_effect=Exception("never saved")), patch.object(access, "is_chat_enabled", return_value=True):
            self.assertIn("can_use", access.can_use_pao())
            self.assertIn("ready", __import__("pibiassistant.pibiassistant_chat.api.auth", fromlist=["x"]).get_user_auth_status())

    @patch("frappe.sessions.get_csrf_token", return_value="t")
    def test_callers_follow_the_key(self, _csrf):
        with patch(PW, return_value="secret"):
            self.assertEqual(capabilities.get_capabilities()["version"], "aida")
            self.assertFalse(capabilities.get_capabilities()["features"]["billing"])
            from pibiassistant.pibiassistant_chat.api import auth

            self.assertTrue(auth.get_user_auth_status()["ready"])
            import pibiassistant.www.aida as www

            self.assertTrue(www.get_boot()["aida_mode"])
        with patch(PW, return_value=None):
            import pibiassistant.www.aida as www

            self.assertFalse(www.get_boot()["aida_mode"])


if __name__ == "__main__":
    unittest.main()
