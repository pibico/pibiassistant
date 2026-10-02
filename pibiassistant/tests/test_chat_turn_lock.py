"""The per-session turn lock must be released on every exit of an AIDA relay."""

from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.api.chat import aida_stream, relay
from pibiassistant.tests.base_test import BaseAssistantTest

SID = "zz-turn-lock-test"


class TestChatTurnLock(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        aida_stream.release_turn(SID)
        self.addCleanup(aida_stream.release_turn, SID)

    def _run(self, fn, *args, **kw):
        with (
            patch.object(frappe, "init"),
            patch.object(frappe, "connect"),
            patch.object(frappe, "destroy"),
            patch.object(frappe, "set_user"),
            patch.object(frappe.db, "commit"),
            patch.object(relay, "_emit_socket_event") as emit,
            patch("pibiassistant.pibiassistant_chat.api.auth._ar_user_id", return_value="u@example.com"),
            patch("pibiassistant.pibiassistant_chat.api.chat.aida_stream.is_aida_mode", return_value=True),
        ):
            fn(*args, **kw)
        return emit

    def test_resume_with_nothing_pending_releases_turn(self):
        self.assertTrue(aida_stream.acquire_turn(SID))
        with patch("pibiassistant.pibiassistant_chat.api.chat.aida_tools.peek_pending", return_value=None):
            emit = self._run(relay._relay_ar_interrupt_resume, SID, [], "Administrator", "demo.pibico.es")
        self.assertEqual(emit.call_args[0][1]["event"], "stream_error")
        self.assertFalse(aida_stream.is_turn_active(SID))

    def test_stream_failing_before_its_try_releases_turn(self):
        self.assertTrue(aida_stream.acquire_turn(SID))
        with patch("pibiassistant.pibiassistant_chat.api.aida._get_aida_config", side_effect=RuntimeError("boom")):
            self._run(relay._relay_ar_stream, SID, "hi", "hi", {}, None, "Administrator", "demo.pibico.es")
        self.assertFalse(aida_stream.is_turn_active(SID))
