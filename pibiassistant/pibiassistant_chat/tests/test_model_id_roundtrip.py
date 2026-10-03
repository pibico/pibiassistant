# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The chosen model survives the round trip on the AIDA relay.

Outbound, a HITL resume has to carry the model the turn was sent with, and only
an explicit user choice travels (auto mode sends nothing). Inbound, the relay
announces the model on stream_start under the key the SPA reads: ``model_id``.
The resume also writes to the server-owned pending message, never a client id.
"""

import unittest

import frappe
from unittest.mock import MagicMock, patch

from pibiassistant.pibiassistant_chat.api.chat import aida_stream, aida_tools, messages, relay


_turn_lock = patch("pibiassistant.pibiassistant_chat.api.chat.messages.acquire_turn_waiting", return_value=True)


def setUpModule():
    # In AIDA mode send/resume/continue take a Redis turn lock the patched relay never releases,
    # which made every later test in the run fail with "still answering".
    _turn_lock.start()


def tearDownModule():
    _turn_lock.stop()


MODEL = "claude-opus-4-1"




class TestModelReachesTheResumeRelay(unittest.TestCase):
    def _resume(self, **kwargs):
        with patch.object(messages._relay_pool, "submit") as submit, patch(
            "pibiassistant.pibiassistant_chat.api.settings.can_use_pao",
            return_value={"can_use": True},
        ), patch.object(messages, "_is_processing_restricted", return_value=False):
            messages.resume_interrupt(
                session_id="s1",
                interrupt_response='[{"interruptId": "i1", "response": "approve"}]',
                **kwargs,
            )
        return submit.call_args[1]

    def test_an_explicit_choice_reaches_the_relay(self):
        self.assertEqual(self._resume(model_id=MODEL).get("model_id"), MODEL)

    def test_auto_mode_reaches_the_relay_as_absence(self):
        self.assertIsNone(self._resume().get("model_id"))


class TestAidaRelayCarriesTheModel(unittest.TestCase):
    def _run(self, **kwargs):
        emitted = []
        run_tool_turn = MagicMock(
            return_value={
                "text": "ok",
                "model": "",
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "tool_calls": [],
            }
        )
        with (
            patch("pibiassistant.pibiassistant_chat.api.aida._get_aida_config", return_value=("https://x", "k", "def", "defmodel")),
            patch("pibiassistant.pibiassistant_chat.api.llm_config.backend_mode", return_value="aida"),
            patch.object(aida_tools, "tools_enabled", return_value=True),
            patch.object(aida_tools, "chat_tool_specs", return_value=[{"function": {"name": "t"}}]),
            patch.object(aida_tools, "run_tool_turn", run_tool_turn),
            patch.object(aida_stream, "_emit_socket_event", side_effect=lambda _s, p: emitted.append(p)),
            patch.object(aida_stream, "_ensure_assistant_msg"),
            patch.object(aida_stream, "get_conversation_id", return_value=None),
            patch.object(aida_stream, "is_cancelled", return_value=False),
        ):
            aida_stream._relay_aida_stream("zz-model-rt", "hi", None, "Administrator", restricted=True, **kwargs)
        return run_tool_turn, emitted

    def test_chosen_model_reaches_tools_and_stream_start(self):
        run, emitted = self._run(model_id="prov/other")
        self.assertEqual(run.call_args.kwargs["provider"], "prov")
        self.assertEqual(run.call_args.kwargs["model"], "other")
        start = [p for p in emitted if p["event"] == "stream_start"][-1]
        self.assertEqual(start["model_id"], "other")

    def test_auto_keeps_the_default_model(self):
        run, emitted = self._run(model_id="auto")
        self.assertEqual(run.call_args.kwargs["model"], "defmodel")
        self.assertEqual([p for p in emitted if p["event"] == "stream_start"][-1]["model_id"], "defmodel")


class TestResumeUsesServerOwnedMessage(unittest.TestCase):
    def _resume(self, client_message_id):
        relay_mock = MagicMock()
        with (
            patch("frappe.init"),
            patch("frappe.connect"),
            patch("frappe.set_user"),
            patch("frappe.destroy"),
            patch.object(relay, "clear_cancel"),
            patch("pibiassistant.pibiassistant_chat.api.chat.aida_stream.is_aida_mode", return_value=True),
            patch("pibiassistant.pibiassistant_chat.api.chat.aida_stream._relay_aida_stream", relay_mock),
            patch("pibiassistant.pibiassistant_chat.api.chat.aida_stream.release_turn") as release,
            patch.object(aida_tools, "peek_pending", return_value={"message_id": "PENDING1"}),
            patch("pibiassistant.pibiassistant_chat.api.auth._ar_user_id", return_value="u"),
        ):
            relay._relay_ar_interrupt_resume(
                session_id="s1",
                interrupt_response=[{"interruptId": "i1", "response": "approve"}],
                user="u@x.com",
                site="site",
                message_id=client_message_id,
                model_id=MODEL,
            )
        return relay_mock, release

    def test_foreign_client_id_is_ignored(self):
        relay_mock, release = self._resume("ZZBBB")
        self.assertEqual(relay_mock.call_args.kwargs["continue_from_message_id"], "PENDING1")
        self.assertEqual(relay_mock.call_args.kwargs["model_id"], MODEL)
        release.assert_called_once_with("s1")


class TestTurnLockRefresh(unittest.TestCase):
    def test_lock_outlives_ttl_while_events_flow(self):
        sid = "zz-lock-refresh"
        aida_stream.release_turn(sid)
        try:
            self.assertTrue(aida_stream.acquire_turn(sid))
            with patch.object(aida_stream, "_TURN_LOCK_TTL", 30):
                aida_stream.refresh_turn(sid)
            ttl = frappe.cache().ttl(aida_stream._turn_lock_key(sid))
            self.assertTrue(0 < ttl <= 30, ttl)
            self.assertFalse(aida_stream.acquire_turn(sid))
        finally:
            aida_stream.release_turn(sid)


if __name__ == "__main__":
    unittest.main()
