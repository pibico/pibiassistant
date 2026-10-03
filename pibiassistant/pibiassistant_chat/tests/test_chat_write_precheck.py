"""A write its own pre-check already knows will be refused shows no approval card; the model gets the reason."""

import json
import unittest
from unittest import mock

import frappe

from pibiassistant.pibiassistant_chat.api.chat import aida_tools


def _call(name, arguments):
    return {"name": name, "arguments": arguments, "tool_id": "t1", "interrupt_id": "i1", "pending": False}


class TestRefusal(unittest.TestCase):
    def test_refusal_extracts_the_reason(self):
        with mock.patch.object(aida_tools, "_tool_preview", return_value="Cancel X. Will be refused: it is a draft"):
            self.assertEqual(aida_tools._refusal("cancel_document", {}), "it is a draft")
        with mock.patch.object(aida_tools, "_tool_preview", return_value="Cancel X. Reverses entries."):
            self.assertIsNone(aida_tools._refusal("cancel_document", {}))

    def test_real_tool_preview_marks_a_doomed_entry(self):
        reason = aida_tools._refusal("create_journal_entry", {"accounts": []})
        self.assertIn("at least two lines", reason)
        self.assertIsNone(aida_tools._refusal("get_document", {}))

    def test_refused_call_is_recorded_as_an_error_and_never_pending(self):
        ctx = {
            "block_builder": mock.Mock(), "emit": mock.Mock(),
            "state": {"collected": []}, "session_id": "s",
        }
        call = _call("create_journal_entry", {"accounts": []})
        aida_tools._execute_call(ctx, call, refused="nope")
        self.assertEqual(call["result_status"], "error")
        self.assertEqual(json.loads(call["result_text"]), {"success": False, "error": "nope"})
        self.assertEqual(ctx["state"]["collected"][0]["status"], "error")
        events = [c.args[0]["event"] for c in ctx["emit"].call_args_list]
        self.assertEqual(events, ["tool_call_start", "tool_call_result"])
        self.assertFalse(call["pending"])


class TestSummaryAfterError(unittest.TestCase):
    def setUp(self):
        self._lang = frappe.local.lang
        frappe.local.lang = "en"

    def tearDown(self):
        frappe.local.lang = self._lang

    def _state(self, *results):
        return {"messages": [{"role": "tool", "tool_name": n, "content": json.dumps(b)} for n, b in results]}

    def test_last_failure_is_reported_plainly(self):
        text = aida_tools._summarize_results(self._state(("list_documents", {"success": True}), ("create_journal_entry", {"success": False, "error": "unbalanced"})))
        self.assertIn("create_journal_entry", text)
        self.assertIn("unbalanced", text)
        self.assertNotIn("raw results", text)

    def test_a_later_success_wins_over_an_earlier_failure(self):
        text = aida_tools._summarize_results(self._state(("a", {"success": False, "error": "x"}), ("b", {"success": True})))
        self.assertIn("raw results", text)

    def test_no_tool_results_gives_nothing(self):
        self.assertEqual(aida_tools._summarize_results({"messages": []}), "")
