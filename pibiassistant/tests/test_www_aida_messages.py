"""The /aida boot payload carries only the translations the SPA can look up."""

from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.aida_mode import is_aida_mode
from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.www import aida as www_aida


class TestWwwAidaMessages(BaseAssistantTest):
    def test_spa_keys_cover_literals_and_dynamic_greeting(self):
        keys = www_aida._spa_keys()
        self.assertIn("Good morning", keys)
        self.assertTrue(len(keys) > 100)

    def test_es_messages_are_limited_to_spa_keys(self):
        messages = www_aida.get_messages("es")
        self.assertTrue(0 < len(messages) < 400)
        self.assertEqual(messages.get("Good morning"), "Buenos días")
        self.assertFalse(set(messages) - www_aida._spa_keys())

    def test_english_has_no_messages(self):
        self.assertEqual(www_aida.get_messages("en"), {})

    def test_js_literal_regex_handles_escapes_and_quotes(self):
        found = [www_aida._unescape_js(a or b) for a, b in www_aida._SPA_LITERAL_RE.findall(
            """__("Say \\"hi\\"") + __('It\\'s ok') + __(variable)""")]
        self.assertEqual(found, ['Say "hi"', "It's ok"])


class TestIsAidaMode(BaseAssistantTest):
    def test_exception_means_not_aida(self):
        with patch("frappe.utils.password.get_decrypted_password", side_effect=RuntimeError("boom")):
            self.assertFalse(is_aida_mode())
            from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

            with patch.object(frappe, "get_single", side_effect=frappe.DoesNotExistError):
                with self.assertRaises(frappe.DoesNotExistError):
                    get_pa_cloud_client()

    def test_key_set_means_aida_and_no_cloud_client(self):
        from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

        with patch("frappe.utils.password.get_decrypted_password", return_value="k"):
            self.assertTrue(is_aida_mode())
            self.assertIsNone(get_pa_cloud_client())
