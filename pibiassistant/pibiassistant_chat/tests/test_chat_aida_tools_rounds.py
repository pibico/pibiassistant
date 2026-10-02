"""AIDA tool loop: the last round asks for text without tools, results are never lost, big results stay valid JSON."""

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.pibiassistant_chat.api.chat import aida_tools

MOD = "pibiassistant.pibiassistant_chat.api.chat.aida_tools"


def _reply(message):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"message": message, "model": "m"}
    return r


def _calls_reply():
    return _reply({"content": "", "tool_calls": [{"function": {"name": "list_documents", "arguments": {}}}]})


def _ctx():
    state = aida_tools._new_state("Administrator", "mid", "p", "m", [{"role": "user", "content": "q"}])
    return {
        "session_id": "ZZ-rounds",
        "api_url": "http://x",
        "api_key": "k",
        "specs": [{"type": "function", "function": {"name": "list_documents"}}],
        "emit": lambda _e: None,
        "block_builder": MagicMock(),
        "state": state,
        "http": aida_tools.requests,
    }


class TestToolRounds(unittest.TestCase):
    def test_tool_only_model_still_gets_a_non_empty_answer_and_a_toolless_last_request(self):
        bodies = []

        def post(_url, json=None, **_k):
            bodies.append(json)
            return _calls_reply()

        with patch(f"{MOD}.requests.post", side_effect=post), patch(
            f"{MOD}._run_tool", return_value=("success", '{"data": [1]}')
        ), patch(f"{MOD}.is_cancelled", return_value=False):
            outcome = aida_tools._loop(_ctx())
        self.assertTrue(outcome["text"].strip())
        self.assertIn("list_documents", outcome["text"])
        self.assertNotIn("tools", bodies[-1])
        self.assertIn("tools", bodies[0])
        self.assertTrue(any(m["content"] == aida_tools._ANSWER_NOW for m in bodies[-1]["messages"]))

    def test_empty_text_after_tools_forces_one_more_toolless_round(self):
        replies = [_calls_reply(), _reply({"content": ""}), _reply({"content": "Final answer"})]
        bodies = []

        def post(_url, json=None, **_k):
            bodies.append(json)
            return replies[len(bodies) - 1]

        with patch(f"{MOD}.requests.post", side_effect=post), patch(
            f"{MOD}._run_tool", return_value=("success", "{}")
        ), patch(f"{MOD}.is_cancelled", return_value=False):
            outcome = aida_tools._loop(_ctx())
        self.assertEqual(outcome["text"], "Final answer")
        self.assertNotIn("tools", bodies[-1])

    def test_upstream_5xx_after_tools_falls_back_to_a_toolless_answer(self):
        bad = MagicMock(status_code=502, text="bad tool call")
        replies = [_calls_reply(), bad, bad, _reply({"content": "Answer from results"})]
        bodies = []

        def post(_url, json=None, **_k):
            bodies.append(json)
            return replies[len(bodies) - 1]

        with patch(f"{MOD}.requests.post", side_effect=post), patch(
            f"{MOD}._run_tool", return_value=("success", "{}")
        ), patch(f"{MOD}.is_cancelled", return_value=False):
            outcome = aida_tools._loop(_ctx())
        self.assertEqual(outcome["text"], "Answer from results")
        self.assertNotIn("tools", bodies[-1])

    def test_system_prompt_has_site_context_and_routing_hints(self):
        prompt = aida_tools._system_prompt("Administrator")
        self.assertIn("Bin", prompt)
        company = frappe.db.get_single_value("Global Defaults", "default_company")
        if company:
            self.assertIn(company, prompt)

    def test_big_result_is_cut_by_rows_and_stays_valid_json(self):
        rows = [{"name": f"DOC-{i}", "title": "x" * 40} for i in range(5000)]
        text = aida_tools._fit_result(json.dumps({"data": rows, "count": 5000}))
        self.assertLessEqual(len(text), aida_tools.MAX_TOOL_RESULT_CHARS)
        parsed = json.loads(text)
        self.assertTrue(parsed["truncated"])
        self.assertEqual(parsed["total"], 5000)
        self.assertEqual(parsed["rows_shown"], len(parsed["data"]))
        self.assertEqual(parsed["count"], 5000)

    def test_bare_list_and_plain_text_stay_valid_json(self):
        self.assertTrue(json.loads(aida_tools._fit_result(json.dumps(list(range(20000)))))["truncated"])
        self.assertTrue(json.loads(aida_tools._fit_result(json.dumps({"s": "y" * 30000})))["truncated"])

    def test_file_tool_is_limited_to_own_or_document_files(self):
        with patch(f"{MOD}.frappe.db.get_value", return_value=frappe._dict(owner="other@x.com", attached_to_doctype=None)):
            self.assertFalse(aida_tools._can_read_file({"file_url": "/private/files/a.pdf"}))
        with patch(
            f"{MOD}.frappe.db.get_value", return_value=frappe._dict(owner="other@x.com", attached_to_doctype="PA Chat Message")
        ):
            self.assertFalse(aida_tools._can_read_file({"file_url": "/private/files/a.pdf"}))
        with patch(f"{MOD}.frappe.db.get_value", return_value=frappe._dict(owner=frappe.session.user, attached_to_doctype=None)):
            self.assertTrue(aida_tools._can_read_file({"file_name": "a.pdf"}))
        self.assertFalse(aida_tools._can_read_file({}))
        self.assertIn("extract_file_content", aida_tools.READ_TOOLS)
        self.assertIn("aggregate_documents", aida_tools.READ_TOOLS)


class TestToolTurnFailure(unittest.TestCase):
    def test_tool_turn_error_after_a_tool_ran_does_not_fall_back_to_a_plain_stream(self):
        from pibiassistant.pibiassistant_chat.api.chat import aida_stream

        def run_tool_turn(**kw):
            kw["block_builder"].add_tool_call_start("t1", "list_documents", {})
            raise RuntimeError("boom")

        emitted = []
        with patch.object(aida_stream, "_open_stream") as open_stream, patch(
            "pibiassistant.pibiassistant_chat.api.aida._get_aida_config", return_value=("http://x", "k", "p", "m")
        ), patch(f"{MOD}.chat_tool_specs", return_value=[{"x": 1}]), patch(f"{MOD}.run_tool_turn", side_effect=run_tool_turn), patch(
            f"{MOD}.tools_enabled", return_value=True
        ), patch.object(aida_stream, "_emit_socket_event", side_effect=lambda _s, p: emitted.append(p)), patch.object(
            aida_stream, "_ensure_assistant_msg"
        ), patch.object(aida_stream, "release_turn"), patch.object(aida_stream.frappe, "log_error"), patch(
            "pibiassistant.pibiassistant_chat.api.chat.relay._persist_partial_assistant_turn"
        ):
            aida_stream._relay_aida_stream("ZZ-fail", "hola", None, "Administrator", restricted=True)
        open_stream.assert_not_called()
        self.assertEqual(emitted[-1]["event"], "stream_error")


if __name__ == "__main__":
    unittest.main()
