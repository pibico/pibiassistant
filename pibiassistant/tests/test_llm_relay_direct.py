"""Direct-provider relay: plain and tool turns through a fake adapter, pause/resume, payloads, gates."""

import json
import uuid
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.pibiassistant_chat.api import aida, llm_config, models
from pibiassistant.pibiassistant_chat.api.chat import aida_stream, aida_tools, direct_stream
from pibiassistant.pibiassistant_chat.api.chat.providers import errors as perr
from pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message import PAChatMessage
from pibiassistant.tests.base_test import BaseAssistantTest

LC = "pibiassistant.pibiassistant_chat.api.llm_config"
FAKE_KEY = "sk-test-FAKE"
SLUG = "zzopenai"


def make_row(**kw):
    row = {
        "name": "zz-row-1",
        "idx": 1,
        "provider_id": "openai",
        "slug": SLUG,
        "label": "ZZ OpenAI fake",
        "enabled": True,
        "base_url": "http://127.0.0.1:9/v1",
        "default_model": "echo-1",
        "extra_models": [],
        "api_version": "",
        "deployment": "",
        "timeout_seconds": 120,
        "max_output_tokens": 0,
        "supports_tools": True,
        "has_key": True,
    }
    row.update(kw)
    return row


class FakeAdapter:
    """Scripted stand-in for a provider adapter (keeps its key private like the real ones)."""

    def __init__(self, chats=None, stream=None, stream_error=None):
        self._key = FAKE_KEY
        self.chats = list(chats or [])
        self.stream = stream
        self.stream_error = stream_error
        self.chat_calls = []

    def chat(self, messages, tools=None, model=None, max_tokens=None, cancel=None, **extra):
        self.chat_calls.append({"messages": json.loads(json.dumps(messages)), "tools": tools, "model": model, "extra": extra})
        step = self.chats.pop(0)
        if isinstance(step, Exception):
            raise step
        return {
            "content": step.get("content", ""),
            "tool_calls": step.get("tool_calls", []),
            "usage": step.get("usage", {"prompt_tokens": 10, "completion_tokens": 5}),
            "model": step.get("model", "echo-1"),
            "finish_reason": "tool_calls" if step.get("tool_calls") else "stop",
            "raw": step.get("raw"),
        }

    def stream_chat(self, messages, tools=None, model=None, max_tokens=None, cancel=None):
        if self.stream_error:
            raise self.stream_error
        yield from self.stream


def tool_call(name, **args):
    return {"name": name, "arguments": args}


class RelayBase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.sid = "zz-direct-" + uuid.uuid4().hex[:8]
        PAChatMessage.create_message(self.sid, "user", "earlier question")
        prev = PAChatMessage.create_message(self.sid, "assistant", "earlier answer")
        frappe.db.set_value("PA Chat Message", prev.name, "message_id", "prev-turn")
        self.user_row = PAChatMessage.create_message(self.sid, "user", "Hello").name
        self.events = []
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.row = make_row()
        settings = MagicMock()
        settings.get.side_effect = lambda k, d=None: {"llm_backend_mode": "Both", "aida_default_provider": "p", "aida_default_model": "m"}.get(k, d)
        enter = self.stack.enter_context
        enter(patch(f"{LC}._settings", return_value=settings))
        enter(patch("pibiassistant.pibiassistant_chat.aida_mode.is_aida_mode", return_value=False))
        enter(patch(f"{LC}.llm_providers", side_effect=lambda enabled_only=False: [self.row]))
        enter(patch.object(direct_stream, "_emit_socket_event", side_effect=lambda sid, data: self.events.append(data)))
        enter(patch.object(aida_stream, "_emit_socket_event", side_effect=lambda sid, data: self.events.append(data)))
        enter(patch.object(direct_stream, "refresh_turn"))
        enter(patch.object(aida_stream, "refresh_turn"))
        enter(patch.object(aida_tools, "tools_enabled", return_value=False))
        enter(patch("pibiassistant.pibiassistant_chat.api.chat.relay._emit_socket_event", side_effect=lambda sid, data: self.events.append(data)))
        enter(patch("frappe.translate.get_user_lang", return_value="en"))

    def adapter(self, adapter):
        self.stack.enter_context(
            patch("pibiassistant.pibiassistant_chat.api.chat.providers.get_provider", return_value=adapter, create=True)
        )
        return adapter

    def run_turn(self, message="Hello", model_id=f"d:{SLUG}/echo-1", **kw):
        aida_stream._relay_aida_stream(self.sid, message, self.user_row, frappe.session.user, model_id=model_id, **kw)

    def by_event(self, name):
        return [e for e in self.events if e.get("event") == name]

    def assistant_row(self, **filters):
        return frappe.get_all(
            "PA Chat Message",
            {"session_id": self.sid, "role": "assistant", "message_id": ["is", "set"], **filters},
            ["name", "content", "model", "prompt_tokens", "completion_tokens", "duration_ms", "errored", "aborted"],
            order_by="creation desc",
        )[0]


class TestDirectPlainTurn(RelayBase):
    def test_stream_persists_model_tokens_and_duration(self):
        self.adapter(
            FakeAdapter(
                stream=[
                    {"type": "chunk", "content": "ECO: "},
                    {"type": "chunk", "content": "Hello"},
                    {"type": "done", "usage": {"prompt_tokens": 12, "completion_tokens": 3}, "model": "echo-1", "finish_reason": "stop"},
                ]
            )
        )
        self.run_turn()
        start = self.by_event("stream_start")[0]
        self.assertEqual(start["model_id"], f"{SLUG}/echo-1")
        self.assertEqual("".join(e["chunk"] for e in self.by_event("stream_chunk")), "ECO: Hello")
        done = self.by_event("stream_complete")[0]
        self.assertEqual(done["full_response"], "ECO: Hello")
        self.assertEqual((done["prompt_tokens"], done["completion_tokens"], done["credits_used"]), (12, 3, 0))
        row = self.assistant_row()
        self.assertEqual(row.content, "ECO: Hello")
        self.assertEqual(row.model, f"{SLUG}/echo-1")
        self.assertEqual((row.prompt_tokens, row.completion_tokens), (12, 3))
        self.assertIsNotNone(row.duration_ms)
        self.assertFalse(row.errored)

    def test_history_is_rebuilt_and_sent(self):
        seen = {}

        class Spy(FakeAdapter):
            def stream_chat(self, messages, **kw):
                seen["messages"] = messages
                yield {"type": "chunk", "content": "ok"}
                yield {"type": "done", "usage": {}, "model": "echo-1", "finish_reason": "stop"}

        self.adapter(Spy())
        self.run_turn()
        roles = [m["role"] for m in seen["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])
        self.assertEqual(seen["messages"][-1]["content"], "Hello")
        self.assertEqual(seen["messages"][1]["content"], "earlier question")

    def test_length_marks_truncated(self):
        self.adapter(
            FakeAdapter(
                stream=[
                    {"type": "chunk", "content": "partial"},
                    {"type": "done", "usage": {}, "model": "echo-1", "finish_reason": "length"},
                ]
            )
        )
        self.run_turn()
        done = self.by_event("stream_complete")[0]
        self.assertTrue(done["truncated"])
        self.assertEqual(done["stop_reason"], "max_tokens")

    def test_provider_error_is_friendly_and_keyless(self):
        self.adapter(FakeAdapter(stream_error=perr.ProviderAuthError(f"bad {FAKE_KEY}", status=401, label="ZZ OpenAI fake")))
        with patch("frappe.log_error") as log:
            self.run_turn()
        err = self.by_event("stream_error")[0]["error"]
        self.assertIn("ZZ OpenAI fake rejected the API key", err)
        self.assertNotIn(FAKE_KEY, json.dumps(self.events))
        self.assertNotIn("127.0.0.1", err)
        self.assertEqual(log.call_args.kwargs["title"], "LLM Provider Error")
        self.assertNotIn(FAKE_KEY, str(log.call_args))
        self.assertEqual(self.assistant_row().errored, 1)

    def test_error_after_chunks_keeps_partial(self):
        self.adapter(
            FakeAdapter(stream=[{"type": "chunk", "content": "half"}, {"type": "error", "kind": "overloaded", "message": "Overloaded now"}])
        )
        self.run_turn()
        err = self.by_event("stream_error")[0]
        self.assertEqual(err["error"], "Overloaded now")
        self.assertEqual(err["partial_response"], "half")

    def test_empty_answer_and_cut_off(self):
        self.adapter(FakeAdapter(stream=[{"type": "done", "usage": {}, "model": "m", "finish_reason": "stop"}]))
        self.run_turn()
        self.assertIn("empty answer", self.by_event("stream_error")[0]["error"])
        self.events.clear()
        self.adapter(FakeAdapter(stream=[{"type": "chunk", "content": "abc"}]))
        self.run_turn()
        self.assertIn("cut off", self.by_event("stream_error")[0]["error"])

    def test_unavailable_provider_message(self):
        self.row = make_row(enabled=False)
        self.run_turn(model_id=f"d:{SLUG}/echo-1")  # falls back to the default choice, which is none
        self.assertIn("No AI provider is configured", self.by_event("stream_error")[0]["error"])

    def test_cancel_before_first_event(self):
        self.adapter(FakeAdapter(stream=[{"type": "chunk", "content": "x"}, {"type": "done", "usage": {}}]))
        with patch.object(direct_stream, "is_cancelled", return_value=True):
            self.run_turn()
        self.assertEqual(len(self.by_event("stream_aborted")), 1)

    def test_clears_aida_conversation_after_direct_turn(self):
        self.adapter(
            FakeAdapter(stream=[{"type": "chunk", "content": "ok"}, {"type": "done", "usage": {}, "model": "m", "finish_reason": "stop"}])
        )
        with patch.object(direct_stream, "clear_conversation_id") as clear:
            self.run_turn()
        clear.assert_called_once_with(self.sid)


class TestDirectToolTurn(RelayBase):
    def setUp(self):
        super().setUp()
        enter = self.stack.enter_context
        enter(patch.object(aida_tools, "tools_enabled", return_value=True))
        specs = [
            {"type": "function", "function": {"name": n, "description": "d", "parameters": {"type": "object", "properties": {}}}}
            for n in ("get_doctype_info", "create_document")
        ]
        enter(patch.object(aida_tools, "chat_tool_specs", return_value=specs))
        enter(patch.object(aida_tools, "_run_tool", return_value=("success", '{"fields": 3}')))
        enter(patch.object(aida_tools, "write_tools_enabled", return_value=True))
        # No peek here: a miss would be memoised in frappe.local.cache and hide the later save.
        self.addCleanup(frappe.cache().delete_value, aida_tools._pending_key(self.sid))

    def test_round_trip(self):
        ad = self.adapter(
            FakeAdapter(
                chats=[
                    {"tool_calls": [tool_call("get_doctype_info", doctype="User")], "usage": {"prompt_tokens": 20, "completion_tokens": 4}},
                    {"content": "RESULTADO: 3 fields", "usage": {"prompt_tokens": 30, "completion_tokens": 6}},
                ]
            )
        )
        self.run_turn(message="usa la herramienta")
        self.assertEqual(len(self.by_event("tool_call_start")), 1)
        self.assertEqual(self.by_event("tool_call_result")[0]["status"], "success")
        done = self.by_event("stream_complete")[0]
        self.assertEqual(done["full_response"], "RESULTADO: 3 fields")
        self.assertEqual((done["prompt_tokens"], done["completion_tokens"]), (50, 10))
        self.assertEqual(done["model_id"], f"{SLUG}/echo-1")
        second = ad.chat_calls[1]["messages"]
        self.assertEqual(second[-2]["role"], "assistant")
        self.assertEqual(second[-2]["tool_calls"][0]["function"]["arguments"], {"doctype": "User"})
        self.assertEqual(second[-1]["role"], "tool")
        self.assertEqual(second[-1]["tool_name"], "get_doctype_info")
        self.assertEqual(ad.chat_calls[0]["model"], "echo-1")
        row = self.assistant_row()
        self.assertEqual(row.model, f"{SLUG}/echo-1")
        self.assertEqual((row.prompt_tokens, row.completion_tokens), (50, 10))

    def test_approval_pause_resume_keeps_backend_and_no_key(self):
        ad = self.adapter(
            FakeAdapter(
                chats=[
                    {"tool_calls": [tool_call("create_document", doctype="ToDo")], "raw": [{"type": "thinking", "signature": "s"}]},
                    {"content": "Created."},
                ]
            )
        )
        self.run_turn(message="create a todo")
        card = self.by_event("approval_required")[0]
        self.assertTrue(self.by_event("stream_complete")[0]["interrupted"])
        state = aida_tools.peek_pending(self.sid, frappe.session.user)
        cache_raw = json.dumps(state)
        self.assertEqual(state["backend"], {"kind": "direct", "slug": SLUG})
        self.assertNotIn(FAKE_KEY, cache_raw)
        self.assertEqual(state["messages"][-1]["_raw"], [{"type": "thinking", "signature": "s"}])
        self.events.clear()
        # the picker now says AIDA: the paused turn still resumes on its own backend
        self.run_turn(
            message="", model_id="openai/gpt-x",
            resume_responses=[{"interruptId": card["interrupts"][0]["id"], "response": "approve"}],
        )
        self.assertEqual(self.by_event("stream_complete")[0]["full_response"], "Created.")
        self.assertEqual(len(ad.chat_calls), 2)
        self.assertEqual(ad.chat_calls[1]["messages"][-1]["role"], "tool")

    def test_resume_with_provider_gone_expires(self):
        self.adapter(FakeAdapter(chats=[{"tool_calls": [tool_call("create_document", doctype="ToDo")]}]))
        self.run_turn(message="create a todo")
        card = self.by_event("approval_required")[0]
        self.events.clear()
        self.row = make_row(enabled=False)
        self.run_turn(
            message="", resume_responses=[{"interruptId": card["interrupts"][0]["id"], "response": "approve"}]
        )
        self.assertTrue(self.by_event("stream_error"))

    def test_supports_tools_off_runs_plain(self):
        self.row = make_row(supports_tools=False)
        self.adapter(
            FakeAdapter(stream=[{"type": "chunk", "content": "plain"}, {"type": "done", "usage": {}, "model": "m", "finish_reason": "stop"}])
        )
        self.run_turn()
        self.assertEqual(self.by_event("stream_complete")[0]["full_response"], "plain")

    def test_provider_error_in_tool_turn_fails_cleanly(self):
        self.adapter(FakeAdapter(chats=[perr.ProviderRateLimitError("", status=429, label="ZZ OpenAI fake")]))
        self.run_turn()
        self.assertIn("too many requests", self.by_event("stream_error")[0]["error"])


class TestChatRoundDirect(RelayBase):
    def ctx(self, adapter):
        return {"session_id": self.sid, "adapter": adapter, "specs": [{"x": 1}], "backend": {"kind": "direct", "slug": SLUG}}

    def state(self, collected=False):
        return {"messages": [{"role": "user", "content": "q"}], "model": "echo-1", "collected": [1] if collected else []}

    def test_unsupported_tools_retries_without_tools(self):
        ad = FakeAdapter(chats=[perr.ProviderUnsupportedError("no tools", feature="tools", label="L"), {"content": "plain"}])
        ctx = self.ctx(ad)
        data = aida_tools._chat_round_direct(ctx, self.state(), False)
        self.assertEqual(data["message"]["content"], "plain")
        self.assertTrue(ctx["no_tools"])
        self.assertIsNone(ad.chat_calls[1]["tools"])

    def test_server_error_after_tools_forces_answer(self):
        ad = FakeAdapter(chats=[perr.ProviderServerError("", status=500, label="L")])
        st = self.state(collected=True)
        with patch("frappe.log_error"):
            self.assertIsNone(aida_tools._chat_round_direct(self.ctx(ad), st, False))
        self.assertTrue(st["force_answer"])

    def test_server_error_first_round_raises(self):
        ad = FakeAdapter(chats=[perr.ProviderServerError("", status=500, label="L")])
        with self.assertRaises(perr.ProviderServerError):
            aida_tools._chat_round_direct(self.ctx(ad), self.state(), False)

    def test_cancelled_returns_aborted(self):
        ad = FakeAdapter(chats=[perr.ProviderCancelled()])
        self.assertTrue(aida_tools._chat_round_direct(self.ctx(ad), self.state(), False)["_aborted"])

    def test_raw_dropped_sends_thinking_disabled(self):
        ad = FakeAdapter(chats=[{"content": "x"}])
        st = self.state()
        st["raw_dropped"] = True
        aida_tools._chat_round_direct(self.ctx(ad), st, False)
        self.assertEqual(ad.chat_calls[0]["extra"], {"_thinking_disabled": True})

    def test_oversized_raw_is_dropped_from_state(self):
        big = [{"type": "thinking", "thinking": "x" * (aida_tools.RAW_MAX_CHARS + 10)}]
        ad = FakeAdapter(chats=[{"tool_calls": [tool_call("get_doctype_info")], "raw": big}, {"content": "done"}])
        ctx = {
            **self.ctx(ad),
            "state": aida_tools._new_state("Administrator", "m1", SLUG, "echo-1", [{"role": "user", "content": "q"}], {"kind": "direct", "slug": SLUG}),
            "emit": lambda p: None,
            "block_builder": MagicMock(),
        }
        with patch.object(aida_tools, "_execute_call", side_effect=lambda c, call: call.update(result_text="{}", result_status="success")), patch.object(
            aida_tools, "_save_pending"
        ):
            aida_tools._loop(ctx)
        self.assertTrue(ctx["state"]["raw_dropped"])
        self.assertNotIn("_raw", ctx["state"]["messages"][1])


class TestAidaRoundUnchanged(BaseAssistantTest):
    def test_aida_body_and_headers(self):
        sent = {}

        class Http:
            def post(self, url, json=None, headers=None, timeout=None):
                sent.update(url=url, body=json, headers=headers, timeout=timeout)
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"message": {"content": "ok"}}
                return r

        msgs = [{"role": "user", "content": "q"}]
        state = {"provider": "", "model": "m", "messages": msgs, "collected": []}
        ctx = {"api_key": "k", "api_url": "https://aida.example", "http": Http(), "specs": [{"s": 1}], "backend": None}
        out = aida_tools._chat_round(ctx, state, False)
        self.assertEqual(out, {"message": {"content": "ok"}})
        self.assertEqual(sent["url"], "https://aida.example/api/v1/llm/chat")
        self.assertEqual(sent["body"], {"provider": "ollama", "model": "m", "messages": msgs, "max_tokens": 4096, "tools": [{"s": 1}]})
        self.assertEqual(sent["headers"], {"X-API-Key": "k", "Content-Type": "application/json"})
        self.assertEqual(sent["timeout"], (10, 120))
        sent.clear()
        aida_tools._chat_round(ctx, state, True)
        self.assertNotIn("tools", sent["body"])


class TestPayloadsAndGates(RelayBase):
    def test_get_available_models_per_mode(self):
        aida_ok = {"success": True, "models": [{"model_id": "openai/g", "provider": "openai"}]}
        direct = [{"model_id": f"d:{SLUG}/echo-1", "provider": "ZZ OpenAI fake (direct)"}]
        with patch.object(models, "_aida_models", return_value=aida_ok), patch(f"{LC}.direct_models", return_value=direct):
            out = models.get_available_models()
            self.assertEqual([m["model_id"] for m in out["models"]], [f"d:{SLUG}/echo-1"])
        with patch("pibiassistant.pibiassistant_chat.aida_mode.is_aida_mode", return_value=True), patch.object(
            models, "_aida_models", return_value=aida_ok
        ), patch(f"{LC}.direct_models", return_value=direct) as dm:
            out = models.get_available_models(refresh=1)
            self.assertEqual([m["model_id"] for m in out["models"]], ["openai/g", f"d:{SLUG}/echo-1"])
            self.assertEqual(out["models_by_tier"]["Standard"], out["models"])
            self.assertEqual(out["auto_mode"]["model_id"], "auto")
            self.assertEqual(out["auto_mode"]["description"], "Default model")
            dm.assert_called_once_with(refresh=True)

    def test_both_aida_error_with_direct_models_still_succeeds(self):
        with patch("pibiassistant.pibiassistant_chat.aida_mode.is_aida_mode", return_value=True), patch.object(
            models, "_aida_models", return_value={"success": False, "models": [], "error": "AIDA down"}
        ), patch(f"{LC}.direct_models", return_value=[]):
            out = models.get_available_models()
            self.assertFalse(out["success"])
            self.assertEqual(out["error"], "AIDA down")

    def test_aida_only_payload_is_unchanged(self):
        settings = MagicMock()
        settings.get.return_value = "AIDA only"
        with patch(f"{LC}._settings", return_value=settings), patch(
            "pibiassistant.pibiassistant_chat.aida_mode.is_aida_mode", return_value=True
        ), patch.object(models, "_aida_models", return_value={"sentinel": 1}):
            self.assertEqual(models.get_available_models(), {"sentinel": 1})
        with patch(f"{LC}._settings", return_value=settings), patch(
            "pibiassistant.pibiassistant_chat.aida_mode.is_aida_mode", return_value=False
        ):
            self.assertIn("error", models.get_available_models())

    def test_overview_lists_provider_without_path_or_credentials(self):
        self.row = make_row(base_url="https://user:pw@api.example.com:8443/v1/secret?x=1")
        out = aida.get_overview()
        self.assertEqual(out["backend_mode"], "both")
        svc = out["services"]["ZZ OpenAI fake"]
        self.assertEqual(svc, {"url": "https://api.example.com:8443", "configured": True})
        self.assertNotIn("pw", json.dumps(out))
        self.assertIn("Chat", out["services"])

    def test_overview_direct_mode_omits_chat(self):
        self.stack.enter_context(patch(f"{LC}.backend_mode", return_value="direct"))
        self.assertNotIn("Chat", aida.get_overview()["services"])

    def test_test_connections_adds_label_api_keys(self):
        self.stack.enter_context(patch(f"{LC}.prepared_provider_test", return_value=lambda: {"ok": True, "detail": "https://x - 3 models", "error": ""}))
        self.stack.enter_context(
            patch.object(aida, "_health_targets", return_value=(("Chat API", "", ""), ("Convert API", "", ""), ("Voice API", "", "")))
        )
        out = aida.test_connections(refresh=1)
        self.assertEqual(out["ZZ OpenAI fake API"]["ok"], True)
        self.assertEqual(out["Chat API"], {"ok": False, "error": "Not configured"})
        self.assertEqual(llm_config.cached_provider_status()["ZZ OpenAI fake API"]["ok"], True)
        self.assertIn("ZZ OpenAI fake API", aida.cached_connection_status())
        frappe.cache().delete_value("pa_llm_health:zz-row-1")

    def test_test_connections_unusable_row_is_not_configured(self):
        self.row = make_row(has_key=False)
        self.stack.enter_context(
            patch.object(aida, "_health_targets", return_value=(("Chat API", "", ""), ("Convert API", "", ""), ("Voice API", "", "")))
        )
        out = aida.test_connections(refresh=1)
        self.assertEqual(out["ZZ OpenAI fake API"], {"ok": False, "error": "Not configured"})
        frappe.cache().delete_value("pa_llm_health:zz-row-1")

    def test_aida_status_reports_providers_without_keys(self):
        with patch.object(aida_tools, "chat_tool_specs", return_value=[]):
            status = aida_tools.aida_status("Administrator")
        self.assertEqual(status["backend_mode"], "both")
        self.assertEqual(status["direct_providers"], [{"label": "ZZ OpenAI fake", "enabled": True, "configured": True}])

    def test_aida_status_aida_only_has_no_provider_keys(self):
        settings = MagicMock()
        settings.get.return_value = "AIDA only"
        with patch(f"{LC}._settings", return_value=settings), patch.object(aida_tools, "chat_tool_specs", return_value=[]):
            status = aida_tools.aida_status("Administrator")
        self.assertNotIn("backend_mode", status)
        self.assertNotIn("direct_providers", status)

    def test_chat_gate_is_llm_ready(self):
        from pibiassistant.pibiassistant_chat.api import _helpers

        self.assertIs(_helpers._aida_mode, llm_config.llm_ready)
        self.assertTrue(llm_config.llm_ready())  # direct row usable, AIDA key absent


class TestConvertWithoutChatGate(RelayBase):
    def test_convert_document_does_not_need_chat_gate(self):
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": "zz-conv.txt", "content": b"hello", "is_private": 1}
        ).insert(ignore_permissions=True)
        self.addCleanup(lambda: frappe.delete_doc("File", file_doc.name, force=1, ignore_permissions=True))
        with patch("pibiassistant.pibiassistant_chat.api.settings.can_use_pao", return_value={"can_use": False}), patch.object(
            aida, "convert_bytes_to_markdown", return_value=("# md", "")
        ):
            out = aida.convert_document(file_url=file_doc.file_url)
        self.assertEqual(out, {"ok": True, "markdown": "# md", "filename": "zz-conv.txt"})

    def test_convert_missing_config_message(self):
        with patch.object(aida, "_get_convert_config", return_value=("", "")):
            md, err = aida.convert_bytes_to_markdown(b"x", "a.txt")
        self.assertEqual(md, "")
        self.assertIn("Document conversion is not configured", err)

    def test_guest_is_refused(self):
        with patch("frappe.session", MagicMock(user="Guest")):
            with self.assertRaises(frappe.PermissionError):
                aida._assert_chat_user()

    def test_user_without_role_is_refused(self):
        with patch("frappe.get_roles", return_value=["Guest"]), patch("frappe.session", MagicMock(user="nobody@example.com")):
            with self.assertRaises(frappe.PermissionError):
                aida._assert_chat_user()


class TestNoProviderGuard(BaseAssistantTest):
    def test_direct_mode_without_usable_provider_fails_like_unconfigured(self):
        sid = "zz-none-" + uuid.uuid4().hex[:8]
        user_row = PAChatMessage.create_message(sid, "user", "hi").name
        events = []
        settings = MagicMock()
        settings.get.side_effect = lambda k, d=None: "Direct providers" if k == "llm_backend_mode" else d
        with patch(f"{LC}._settings", return_value=settings), patch(f"{LC}.llm_providers", return_value=[]), patch.object(
            aida_stream, "_emit_socket_event", side_effect=lambda s, d: events.append(d)
        ):
            aida_stream._relay_aida_stream(sid, "hi", user_row, frappe.session.user, model_id="auto")
        self.assertIn("No AI provider is configured", events[0]["error"])
        self.assertEqual(frappe.get_all("PA Chat Message", {"session_id": sid, "errored": 1}, pluck="name").__len__(), 1)
