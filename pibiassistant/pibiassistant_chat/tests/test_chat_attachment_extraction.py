"""Attachment conversion leaves the web request, runs in parallel, and is size-capped; resume payloads are validated."""

import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.api.chat import aida_stream, helpers, messages

MOD = "pibiassistant.pibiassistant_chat.api.chat.messages"
EXTRACT = "pibiassistant.plugins.data_science.tools.extract_file_content.ExtractFileContent.execute"


def _files(n):
    return [
        frappe._dict(name=f"F{i}", file_name=f"a{i}.pdf", file_url=f"/files/a{i}.pdf", file_size=10)
        for i in range(n)
    ]


class TestExtractionCaps(unittest.TestCase):
    def test_each_file_and_the_total_are_capped_with_a_marker(self):
        big = {"success": True, "content": "x" * 500_000}
        with patch.object(helpers.frappe, "get_all", return_value=_files(5)), patch(EXTRACT, return_value=big):
            out = helpers._extract_file_attachments("MSG")
        self.assertLess(len(out), helpers.MAX_ATTACHMENT_CHARS + 2000)
        self.assertIn("truncated", out)
        self.assertIn("left out", out)

    def test_small_files_are_untouched(self):
        with patch.object(helpers.frappe, "get_all", return_value=_files(2)), patch(
            EXTRACT, return_value={"success": True, "content": "hello"}
        ):
            out = helpers._extract_file_attachments("MSG")
        self.assertEqual(out.count("hello"), 2)
        self.assertNotIn("truncated", out)

    def test_parallel_conversion_overlaps_the_waits(self):
        def slow(_self, _args):
            time.sleep(1)
            return {"success": True, "content": "ok"}

        with patch.object(helpers.frappe, "get_all", return_value=_files(3)), patch(EXTRACT, slow):
            started = time.monotonic()
            out = helpers._extract_file_attachments("MSG", parallel=True)
            elapsed = time.monotonic() - started
        self.assertEqual(out.count("Content:\nok"), 3)
        self.assertLess(elapsed, 2.5, "three 1 s conversions must overlap")


class TestSendDefersExtraction(unittest.TestCase):
    def test_aida_send_returns_before_any_conversion(self):
        user_msg = SimpleNamespace(name="MSG-1")
        with (
            patch(f"{MOD}.is_aida_mode", return_value=True),
            patch("pibiassistant.pibiassistant_chat.api.settings.can_use_pao", return_value={"can_use": True}),
            patch.object(messages, "_assert_session_owner"),
            patch.object(messages, "_relay_pool") as pool,
            patch.object(messages, "acquire_turn_waiting", return_value=True),
            patch.object(messages, "_is_processing_restricted", return_value=False),
            patch.object(messages, "_attach_files_to_message"),
            patch.object(messages, "clear_cancel"),
            patch.object(messages.frappe, "get_all", return_value=[]),
            patch.object(messages.frappe.db, "commit"),
            patch(
                "pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message.PAChatMessage.create_message",
                return_value=user_msg,
            ),
            patch(
                "pibiassistant.pibiassistant_chat.doctype.pa_chat_session_state.pa_chat_session_state."
                "PAChatSessionState.load_wire",
                return_value=None,
            ),
            patch.object(messages, "_extract_file_attachments", side_effect=AssertionError("ran in the request")),
        ):
            started = time.monotonic()
            result = messages.send_message("ZZ-defer", "resume esto", file_urls='["/files/a.pdf"]')
            self.assertLess(time.monotonic() - started, 0.2)
        self.assertEqual(result["status"], "processing")
        self.assertIs(pool.submit.call_args.kwargs["extract_files"], True)

    def test_relay_adds_the_extracted_text_after_stream_start(self):
        seen = {}
        emitted = []

        def run_tool_turn(**kw):
            seen["message"] = kw["message"]
            kw["block_builder"].add_tool_call_start("t1", "list_documents", {})
            raise RuntimeError("stop here")

        with (
            patch(
                "pibiassistant.pibiassistant_chat.api.aida._get_aida_config",
                return_value=("http://x", "k", "p", "m"),
            ),
            patch(
                "pibiassistant.pibiassistant_chat.api.chat.aida_tools.chat_tool_specs", return_value=[{"x": 1}]
            ),
            patch("pibiassistant.pibiassistant_chat.api.chat.aida_tools.run_tool_turn", side_effect=run_tool_turn),
            patch("pibiassistant.pibiassistant_chat.api.chat.aida_tools.tools_enabled", return_value=True),
            patch.object(helpers, "_extract_file_attachments", return_value="[Attached Files]\nSECRET-DOC-TEXT") as ex,
            patch.object(aida_stream, "_emit_socket_event", side_effect=lambda _s, p: emitted.append(p["event"])),
            patch.object(aida_stream, "_ensure_assistant_msg"),
            patch.object(aida_stream, "release_turn"),
            patch.object(aida_stream.frappe, "log_error"),
            patch("pibiassistant.pibiassistant_chat.api.chat.relay._persist_partial_assistant_turn"),
        ):
            aida_stream._relay_aida_stream(
                "ZZ-ex", "pregunta", "MSG-1", "Administrator", restricted=False, extract_files=True
            )
        ex.assert_called_once_with("MSG-1", parallel=True)
        self.assertIn("SECRET-DOC-TEXT", seen["message"])
        self.assertTrue(seen["message"].endswith("pregunta"))
        self.assertEqual(emitted[0], "stream_start")


class TestInterruptResponseShape(unittest.TestCase):
    def test_malformed_payloads_are_rejected_before_the_turn_lock(self):
        bad = (
            '{"interruptId": "a", "response": "approve"}',
            '["approve"]',
            '[{"response": "approve"}]',
            '[{"interruptId": 5, "response": "approve"}]',
            '[{"interruptId": "a", "response": "yes"}]',
            '[{"interruptId": "a", "response": "approve"}, "x"]',
        )
        with (
            patch(f"{MOD}.acquire_turn_waiting") as lock,
            patch(f"{MOD}.is_aida_mode", return_value=True),
            patch.object(messages, "_assert_session_owner"),
        ):
            for payload in bad:
                with self.assertRaises(frappe.ValidationError, msg=payload):
                    messages.resume_interrupt("ZZ-shape", payload)
            lock.assert_not_called()

    def test_valid_payloads_pass_validation(self):
        for answer in ("approve", "rejected", "trust", "session"):
            messages._validate_interrupt_response([{"interruptId": "a", "response": answer}])


if __name__ == "__main__":
    unittest.main()
