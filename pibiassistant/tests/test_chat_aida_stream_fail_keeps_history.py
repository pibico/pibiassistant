"""A failed AIDA turn writes its own errored row and never overwrites the previous answer."""

import uuid
from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.api.chat import aida_stream, relay
from pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message import PAChatMessage
from pibiassistant.tests.base_test import BaseAssistantTest

PREVIOUS = "ZZ previous answer"


class TestChatAidaStreamFailKeepsHistory(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.sid = "zz-fail-" + uuid.uuid4().hex[:8]
        PAChatMessage.create_message(self.sid, "user", "first question")
        prev = PAChatMessage.create_message(self.sid, "assistant", PREVIOUS)
        frappe.db.set_value("PA Chat Message", prev.name, "message_id", "prev-turn")
        self.prev = prev.name
        user = PAChatMessage.create_message(self.sid, "user", "second question")
        self.user_row = user.name

    def _relay(self, ensure=None):
        patches = [
            patch("pibiassistant.pibiassistant_chat.api.aida._get_aida_config", return_value=("", "", "", "")),
            patch.object(aida_stream, "_emit_socket_event"),
            patch.object(aida_stream, "refresh_turn"),
        ]
        if ensure is not None:
            patches.append(patch.object(aida_stream, "_ensure_assistant_msg", ensure))
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        aida_stream._relay_aida_stream(self.sid, "second question", self.user_row, frappe.session.user)

    def _assert_kept(self):
        self.assertEqual(frappe.db.get_value("PA Chat Message", self.prev, "content"), PREVIOUS)
        self.assertFalse(frappe.db.get_value("PA Chat Message", self.prev, "errored"))
        rows = frappe.get_all(
            "PA Chat Message", {"session_id": self.sid, "role": "assistant", "errored": 1}, ["name", "content"]
        )
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(rows[0].name, self.prev)
        self.assertTrue(rows[0].content)
        self.assertNotEqual(rows[0].content, PREVIOUS)

    def test_not_configured_creates_new_errored_row(self):
        self._relay()
        self._assert_kept()

    def test_missing_shell_row_still_creates_new_row(self):
        self._relay(ensure=lambda *a, **k: None)
        self._assert_kept()

    def test_legacy_lookup_without_message_id_still_finds_latest_row(self):
        name = relay._persist_partial_assistant_turn(self.sid, None, "partial", [], [], "", "aborted")
        self.assertEqual(name, self.prev)
