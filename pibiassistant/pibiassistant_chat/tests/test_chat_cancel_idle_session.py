"""Stop on an idle session must not rewrite the finished answer or leave a cancel flag behind."""

import unittest
from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.api.chat import cancel

MOD = "pibiassistant.pibiassistant_chat.api.chat"


class TestCancelIdleSession(unittest.TestCase):
    def setUp(self):
        self._patches = [
            patch.object(cancel.frappe.db, "get_value", return_value=frappe.session.user),
            patch.object(cancel, "mark_cancelled"),
            patch.object(cancel, "_abort_pending_interactions"),
            patch.object(cancel, "_emit_socket_event"),
            patch(f"{MOD}.aida_stream.is_aida_mode", return_value=True),
            patch("pibiassistant.pibiassistant_chat.pa_cloud_client.get_pa_cloud_client", return_value=None),
        ]
        (self.get_value, self.mark, self.abort, self.emit, self.mode, _client) = [p.start() for p in self._patches]
        for p in self._patches:
            self.addCleanup(p.stop)

    def test_idle_session_is_untouched(self):
        with patch(f"{MOD}.aida_stream.is_turn_active", return_value=False), patch(
            f"{MOD}.aida_tools.peek_pending", return_value=None
        ):
            result = cancel.cancel_stream("ZZ-idle")
        self.assertEqual(result["status"], "cancel_requested")
        self.mark.assert_not_called()
        self.abort.assert_not_called()

    def test_live_turn_is_flagged_without_rewriting_rows(self):
        with patch(f"{MOD}.aida_stream.is_turn_active", return_value=True), patch(
            f"{MOD}.aida_tools.peek_pending", return_value=None
        ):
            cancel.cancel_stream("ZZ-live")
        self.mark.assert_called_once_with("ZZ-live")
        self.abort.assert_not_called()

    def test_pending_approval_is_aborted_and_discarded(self):
        with patch(f"{MOD}.aida_stream.is_turn_active", return_value=False), patch(
            f"{MOD}.aida_tools.peek_pending", return_value={"user": frappe.session.user}
        ), patch(f"{MOD}.aida_tools.discard_pending") as discard:
            cancel.cancel_stream("ZZ-paused")
        self.abort.assert_called_once()
        discard.assert_called_once_with("ZZ-paused", frappe.session.user)
        self.mark.assert_not_called()


if __name__ == "__main__":
    unittest.main()
