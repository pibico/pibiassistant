"""AIDA chat: the prompt follows the write-tools flag, get_aida_status reports it, history has one source."""

import json
import unittest
from unittest.mock import patch

from pibiassistant.pibiassistant_chat.api.chat import aida_stream, aida_tools

MOD = "pibiassistant.pibiassistant_chat.api.chat.aida_tools"


class TestPromptFollowsFlag(unittest.TestCase):
    def test_write_flag_off_prompt_promises_no_changes_and_no_cards(self):
        with patch(f"{MOD}.write_tools_enabled", return_value=False):
            prompt = aida_tools._system_prompt("Administrator")
        self.assertIn("cannot change data", prompt)
        self.assertNotIn("approval card", prompt)
        self.assertNotIn("attach_file", prompt)
        self.assertIn("get_skill", prompt)

    def test_write_flag_on_prompt_describes_approval_cards(self):
        with patch(f"{MOD}.write_tools_enabled", return_value=True):
            prompt = aida_tools._system_prompt("Administrator")
        self.assertIn("approval card", prompt)
        self.assertNotIn("cannot change data", prompt)

    def test_linked_documents_is_a_read_tool(self):
        self.assertIn("get_linked_documents", aida_tools.READ_TOOLS)
        self.assertNotIn("get_linked_documents", aida_tools.WRITE_TOOLS)


class TestAidaStatusTool(unittest.TestCase):
    def test_status_tool_is_offered_even_with_write_tools_off(self):
        with patch(f"{MOD}.write_tools_enabled", return_value=False):
            names = [s["function"]["name"] for s in aida_tools.chat_tool_specs("Administrator")]
        self.assertIn(aida_tools.STATUS_TOOL, names)
        self.assertNotIn("create_document", names)

    def test_status_reports_flags_tools_roles_and_cached_connections(self):
        health = {"Chat API": {"ok": True}}
        with patch(f"{MOD}.write_tools_enabled", return_value=False), patch("pibiassistant.pibiassistant_chat.api.llm_config.backend_mode", return_value="aida"), patch(
            "pibiassistant.pibiassistant_chat.api.aida.cached_connection_status", return_value=health
        ):
            status, text = aida_tools._run_tool(aida_tools.STATUS_TOOL, {})
        data = json.loads(text)
        self.assertEqual(status, "success")
        self.assertIs(data["write_tools_enabled"], False)
        self.assertEqual(data["connections"], health)
        self.assertIn(aida_tools.STATUS_TOOL, data["enabled_tools"])
        self.assertIn("System Manager", data["user_roles"])
        self.assertNotIn("key", text.lower().replace("keys", ""))

    def test_status_without_a_recent_check_says_so(self):
        with patch("pibiassistant.pibiassistant_chat.api.aida.cached_connection_status", return_value=None):
            self.assertEqual(aida_tools.aida_status("Administrator")["connections"], "not checked recently")


class TestSharedHistory(unittest.TestCase):
    def test_transcript_and_tool_history_read_the_same_turns(self):
        turns = [("user", "q1"), ("assistant", "a1")]
        with patch.object(aida_stream, "recent_turns", return_value=turns):
            transcript = aida_stream._build_transcript("S", None)
        self.assertIn("USER: q1", transcript)
        self.assertIn("ASSISTANT: a1", transcript)
        with patch(f"{MOD}.recent_turns", return_value=turns):
            self.assertEqual(
                aida_tools._history_messages("S", None),
                [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}],
            )

    def test_no_turns_gives_empty_transcript(self):
        with patch.object(aida_stream, "recent_turns", return_value=[]):
            self.assertEqual(aida_stream._build_transcript("S", None), "")


if __name__ == "__main__":
    unittest.main()
