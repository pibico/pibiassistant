"""AIDA tool-turn history, tool offer and connection reuse."""

from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.pibiassistant_chat.api.chat import aida_tools
from pibiassistant.tests.base_test import BaseAssistantTest

SID = "zz-aida-history-test"


class TestAidaToolsHistory(BaseAssistantTest):
    def test_history_skips_errored_and_aborted_rows(self):
        names = []
        try:
            for role, content, errored, aborted in (
                ("user", "question", 0, 0),
                ("assistant", "failure text", 1, 0),
                ("assistant", "partial _(Stopped by user)_", 0, 1),
                ("assistant", "good answer", 0, 0),
            ):
                doc = frappe.get_doc(
                    {
                        "doctype": "PA Chat Message",
                        "session_id": SID,
                        "role": role,
                        "content": content,
                        "user": "Administrator",
                        "errored": errored,
                        "aborted": aborted,
                    }
                ).insert(ignore_permissions=True)
                names.append(doc.name)
            out = aida_tools._history_messages(SID, None)
            self.assertEqual([m["content"] for m in out], ["question", "good answer"])
        finally:
            for n in names:
                frappe.delete_doc("PA Chat Message", n, force=1, ignore_permissions=True)

    def test_get_skill_is_offered_and_prompted(self):
        self.assertIn("get_skill", aida_tools.READ_TOOLS)
        self.assertIn("get_skill", aida_tools._system_prompt("Administrator"))
        names = [s["function"]["name"] for s in aida_tools.chat_tool_specs("Administrator")]
        self.assertIn("get_skill", names)

    def test_plugin_set_read_at_most_twice_for_specs(self):
        from pibiassistant.utils.plugin_manager import PluginPersistence

        with patch.object(PluginPersistence, "_read_enabled_plugins", wraps=PluginPersistence()._read_enabled_plugins) as spy:
            aida_tools.chat_tool_specs("Administrator")
        self.assertLessEqual(spy.call_count, 2)

    def test_one_session_serves_every_round_and_is_closed(self):
        session = MagicMock()
        replies = []
        for content, calls in (
            ("", [{"function": {"name": "list_documents", "arguments": {"doctype": "ToDo"}}}]),
            ("", [{"function": {"name": "list_documents", "arguments": {"doctype": "ToDo"}}}]),
            ("done", []),
        ):
            r = MagicMock(status_code=200)
            r.json.return_value = {"message": {"content": content, "tool_calls": calls}, "model": "m"}
            replies.append(r)
        session.post.side_effect = replies
        with (
            patch.object(aida_tools.requests, "Session", return_value=session),
            patch.object(aida_tools.requests, "post") as bare_post,
            patch.object(aida_tools, "_run_tool", return_value=("success", "{}")),
        ):
            out = aida_tools.run_tool_turn(
                session_id=SID,
                user="Administrator",
                message="hi",
                message_name=None,
                message_id="m1",
                api_url="https://x",
                api_key="k",
                provider="p",
                model="m",
                specs=[{"function": {"name": "list_documents"}}],
                emit=lambda e: None,
                block_builder=MagicMock(),
            )
        self.assertEqual(out["text"], "done")
        self.assertEqual(session.post.call_count, 3)
        bare_post.assert_not_called()
        session.close.assert_called_once()
