"""send_message / resume_interrupt reject malformed input as client errors and resume holds the turn lock."""

import unittest
from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.api.chat import messages

MOD = "pibiassistant.pibiassistant_chat.api.chat.messages"
ALLOW = {"can_use": True}


class TestValidation(unittest.TestCase):
    def setUp(self):
        for p in (
            patch(f"{MOD}.is_aida_mode", return_value=True),
            patch("pibiassistant.pibiassistant_chat.api.settings.can_use_pao", return_value=ALLOW),
            patch.object(messages, "_assert_session_owner"),
            patch.object(messages, "_relay_pool"),
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_bad_session_id_never_reaches_the_db(self):
        with patch.object(messages.frappe, "log_error") as log:
            for sid in ("ZZ" + "a" * 500, "a b", "x/../y", ""):
                with self.assertRaises(frappe.ValidationError):
                    messages.send_message(sid, "hola")
            log.assert_not_called()

    def test_bad_json_params_are_validation_errors_without_error_log(self):
        with patch.object(messages.frappe, "log_error") as log:
            for kw in ({"file_urls": "notjson"}, {"attachments": "{"}, {"context": "}{"}, {"file_urls": "[1]"}):
                with self.assertRaises(frappe.ValidationError):
                    messages.send_message("ZZ-ok", "hola", **kw)
            with self.assertRaises(frappe.ValidationError):
                messages.resume_interrupt("ZZ-ok", "notjson")
            log.assert_not_called()

    def test_resume_holds_the_turn_and_refuses_when_busy(self):
        with patch(f"{MOD}.acquire_turn_waiting", return_value=False), patch.object(messages, "release_turn") as rel:
            with self.assertRaises(frappe.ValidationError):
                messages.resume_interrupt("ZZ-busy", '[{"interruptId": "a", "response": "approve"}]')
            rel.assert_not_called()

    def test_resume_releases_the_turn_if_it_fails_before_the_relay_starts(self):
        with patch(f"{MOD}.acquire_turn_waiting", return_value=True), patch.object(
            messages, "release_turn"
        ) as rel, patch.object(messages, "_is_processing_restricted", side_effect=RuntimeError("secret detail")):
            with self.assertRaises(frappe.ValidationError) as ctx:
                messages.resume_interrupt("ZZ-fail", '[{"interruptId": "a", "response": "approve"}]')
            rel.assert_called_once_with("ZZ-fail")
            self.assertNotIn("secret detail", str(ctx.exception))

    def test_resume_submits_when_the_turn_is_free(self):
        with patch(f"{MOD}.acquire_turn_waiting", return_value=True), patch.object(
            messages, "_is_processing_restricted", return_value=True
        ):
            result = messages.resume_interrupt("ZZ-free", '[{"interruptId": "a", "response": "approve"}]')
        self.assertEqual(result["status"], "processing")
        messages._relay_pool.submit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
