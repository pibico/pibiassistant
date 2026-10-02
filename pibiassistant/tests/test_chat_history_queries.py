"""get_session_messages must load attachments with one File query, not one per message."""

from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message import PAChatMessage
from pibiassistant.tests.base_test import BaseAssistantTest


class TestChatHistoryQueries(BaseAssistantTest):
    def test_attachment_queries_are_constant(self):
        rows = [frappe._dict(name=f"M{i}") for i in range(5)]
        files = [
            frappe._dict(name="F1", file_name="a.pdf", file_url="/a", file_size=1, attached_to_name="M1"),
            frappe._dict(name="F2", file_name="b.pdf", file_url="/b", file_size=2, attached_to_name="M1"),
            frappe._dict(name="F3", file_name="c.pdf", file_url="/c", file_size=3, attached_to_name="M4"),
        ]
        calls = []

        def fake_get_all(doctype, **kw):
            calls.append(doctype)
            return files if doctype == "File" else rows

        with (
            patch("frappe.db.count", return_value=5),
            patch("frappe.get_all", side_effect=fake_get_all),
        ):
            out = PAChatMessage.get_session_messages("S", limit=30)

        self.assertEqual(calls.count("File"), 1)
        by_name = {m.name: m for m in out["messages"]}
        self.assertEqual([f.name for f in by_name["M1"].attachments], ["F1", "F2"])
        self.assertEqual(by_name["M0"].attachments, [])
        self.assertEqual([f.name for f in by_name["M4"].attachments], ["F3"])
        self.assertNotIn("attached_to_name", by_name["M1"].attachments[0])
