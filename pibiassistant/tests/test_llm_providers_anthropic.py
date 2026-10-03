"""Anthropic adapter against the local fake Messages API."""

import pickle
import time

from pibiassistant.pibiassistant_chat.api.chat.providers import (
    ProviderAuthError,
    ProviderCancelled,
    ProviderInvalidRequestError,
    ProviderOverloadedError,
    ProviderRateLimitError,
    get_provider,
)
from pibiassistant.tests import _fakeserver as fs

KEY = fs.FAKE_KEY
HELLO = [{"role": "system", "content": "Eres util"}, {"role": "user", "content": "hola"}]
TOOLS = [{"type": "function", "function": {"name": "get_doctype_info", "description": "d",
                                           "parameters": {"type": "object", "properties": {"doctype": {"type": "string"}}}}},
         {"type": "function", "function": {"name": "other", "description": "d", "parameters": {"type": "object", "properties": {}}}}]


class AnthropicCase(fs.ServerCase):
    KIND = "anthropic"

    def adapter(self, model="echo-1", key=KEY, **kw):
        return get_provider(self.row("anthropic", model, **kw), key=key)

    def body(self, i=-1):
        return self.posts()[i]["body"]


class TestChat(AnthropicCase):
    def test_plain_chat_request_and_usage(self):
        res = self.adapter().chat(HELLO)
        self.assertEqual(res["content"], "ECO: hola")
        self.assertEqual(res["finish_reason"], "stop")
        self.assertIsNone(res["raw"])
        self.assertEqual(res["model"], "echo-1")
        rec = self.posts()[0]
        self.assertTrue(rec["auth_ok"])
        self.assertEqual(rec["headers"]["anthropic-version"], "2023-06-01")
        b = rec["body"]
        self.assertEqual(b["system"], "Eres util")
        self.assertEqual(b["max_tokens"], 8192)
        self.assertEqual([m["role"] for m in b["messages"]], ["user"])
        for banned in ("temperature", "thinking", "tool_choice", "tools"):
            self.assertNotIn(banned, b)
        # input + cache read (3) + cache creation (2) from the fake
        self.assertGreaterEqual(res["usage"]["prompt_tokens"], 6)
        self.assertGreater(res["usage"]["completion_tokens"], 0)

    def test_tool_use_with_thinking_replay_round_trip(self):
        a = self.adapter("think-tool")
        msgs = [{"role": "user", "content": "usa la herramienta"}]
        res = a.chat(msgs, tools=TOOLS)
        self.assertEqual(res["finish_reason"], "tool_calls")
        self.assertEqual(res["tool_calls"], [{"name": "get_doctype_info", "arguments": {"doctype": "User"}}])
        self.assertEqual(res["raw"][0]["type"], "thinking")
        self.assertEqual(res["raw"][0]["signature"], "sig-FAKE-1")
        msgs += [{"role": "assistant", "content": "", "tool_calls": [{"function": res["tool_calls"][0]}], "_raw": res["raw"]},
                 {"role": "tool", "tool_name": "get_doctype_info", "content": "campos de User"}]
        res2 = a.chat(msgs, tools=TOOLS)
        self.assertEqual(res2["content"], "RESULTADO: campos de User")
        sent = self.body()["messages"]
        self.assertEqual(sent[1]["content"], res["raw"])
        self.assertEqual(sent[2]["content"][0]["tool_use_id"], res["raw"][1]["id"])

    def test_dropping_raw_breaks_thinking_replay(self):
        a = self.adapter("think-tool")
        msgs = [{"role": "user", "content": "usa la herramienta"}]
        res = a.chat(msgs, tools=TOOLS)
        msgs += [{"role": "assistant", "content": "", "tool_calls": [{"function": res["tool_calls"][0]}]},
                 {"role": "tool", "tool_name": "get_doctype_info", "content": "x"}]
        with self.assertRaises(ProviderInvalidRequestError):
            a.chat(msgs, tools=TOOLS)
        self.assertEqual(self.body()["messages"][1]["content"][0]["type"], "tool_use")

    def test_thinking_disabled_kwarg_sets_param(self):
        self.adapter().chat(HELLO, _thinking_disabled=True)
        self.assertEqual(self.body()["thinking"], {"type": "disabled"})

    def test_several_tool_results_in_one_user_message(self):
        a = self.adapter("think-tool")
        msgs = [{"role": "user", "content": "multiherramienta"}]
        res = a.chat(msgs, tools=TOOLS)
        self.assertEqual([c["name"] for c in res["tool_calls"]], ["get_doctype_info", "other"])
        msgs += [{"role": "assistant", "content": "", "tool_calls": [{"function": c} for c in res["tool_calls"]], "_raw": res["raw"]},
                 {"role": "tool", "tool_name": "other", "content": "R2"},
                 {"role": "tool", "tool_name": "get_doctype_info", "content": "R1"}]
        res2 = a.chat(msgs, tools=TOOLS)
        self.assertEqual(res2["content"], "RESULTADO: R1 | R2")  # fake orders by tool_result position
        user = self.body()["messages"][2]
        self.assertEqual([b["type"] for b in user["content"]], ["tool_result", "tool_result"])

    def test_tool_turns_flattened_when_no_tools_are_offered(self):
        msgs = [{"role": "user", "content": "herramienta"},
                {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "other", "arguments": {}}}],
                 "_raw": [{"type": "tool_use", "id": "toolu_A", "name": "other", "input": {}}]},
                {"role": "tool", "tool_name": "other", "content": "R"}]
        res = self.adapter().chat(msgs)  # the fake answers 400 if tool blocks reach it without tools
        self.assertIn("ECO", res["content"])
        self.assertNotIn("tool_use", str(self.body()["messages"]))

    def test_errors(self):
        with self.assertRaises(ProviderAuthError):
            self.adapter("fail-401").chat(HELLO)
        self.assertEqual(len(self.posts()), 1)
        fs.reset(self.port)
        with self.assertRaises(ProviderRateLimitError):
            self.adapter("fail-429").chat(HELLO)
        self.assertEqual(len(self.posts()), 3)
        fs.reset(self.port)
        with self.assertRaises(ProviderOverloadedError):
            self.adapter("overloaded").chat(HELLO)
        self.assertEqual(len(self.posts()), 3)

    def test_billing_error_is_quota(self):
        from pibiassistant.pibiassistant_chat.api.chat.providers import ProviderQuotaError

        with self.assertRaises(ProviderQuotaError):
            self.adapter("fail-billing").chat(HELLO)
        self.assertEqual(len(self.posts()), 1)

    def test_key_never_in_exceptions_or_repr(self):
        wrong = "sk-ant-wrong-AAAABBBBCCCC1234"
        a = self.adapter(key=wrong)
        with self.assertRaises(ProviderAuthError) as cm:
            a.chat(HELLO)
        e = cm.exception
        for text in (str(e), e.safe_message, e.user_message(), repr(e), repr(a)):
            self.assertNotIn("AAAABBBBCCCC", text)
        with self.assertRaises(TypeError):
            pickle.dumps(a)

    def test_cancel(self):
        with self.assertRaises(ProviderCancelled):
            self.adapter().chat(HELLO, cancel=lambda: True)


class TestStream(AnthropicCase):
    def test_stream_text_and_usage(self):
        ev = list(self.adapter().stream_chat(HELLO))
        self.assertEqual("".join(e["content"] for e in ev if e["type"] == "chunk"), "ECO: hola")
        done = ev[-1]
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["finish_reason"], "stop")
        self.assertGreater(done["usage"]["prompt_tokens"], 0)
        self.assertGreater(done["usage"]["completion_tokens"], 0)
        self.assertTrue(self.body()["stream"])

    def test_thinking_and_tool_events_ignored(self):
        ev = list(self.adapter("think-tool").stream_chat([{"role": "user", "content": "herramienta"}], tools=TOOLS))
        self.assertEqual([e["type"] for e in ev], ["done"])
        self.assertEqual(ev[-1]["finish_reason"], "tool_calls")

    def test_error_event_after_chunks_is_reported_not_raised(self):
        ev = list(self.adapter("stream-overloaded").stream_chat(HELLO))
        self.assertEqual([e["type"] for e in ev], ["chunk", "chunk", "error"])
        self.assertEqual(ev[-1]["kind"], "overloaded")
        self.assertIn("ZZ Fake", ev[-1]["message"])

    def test_http_error_before_first_chunk_raises(self):
        with self.assertRaises(ProviderOverloadedError):
            list(self.adapter("overloaded").stream_chat(HELLO))

    def test_cancel_mid_stream(self):
        seen = {"c": False}
        out = []
        t0 = time.time()
        for e in self.adapter("slow").stream_chat(HELLO, cancel=lambda: seen["c"]):
            out.append(e)
            if e["type"] == "chunk":
                seen["c"] = True
        self.assertEqual(out[-1], {"type": "cancelled"})
        self.assertLess(time.time() - t0, 6)

    def test_cancel_before_start(self):
        self.assertEqual(list(self.adapter().stream_chat(HELLO, cancel=lambda: True)), [{"type": "cancelled"}])


class TestModels(AnthropicCase):
    def test_pagination_followed(self):
        out = self.adapter().list_models()
        self.assertEqual([m["id"] for m in out], ["claude-test-a", "claude-test-b", "claude-test-c"])
        self.assertEqual(out[0]["label"], "Claude Test A")
        gets = [r for r in fs.requests_log(self.port) if r["method"] == "GET"]
        self.assertEqual(len(gets), 2)
        self.assertEqual(gets[0]["query"]["limit"], "1000")
        self.assertEqual(gets[1]["query"]["after_id"], "claude-test-b")

    def test_test_method(self):
        ok = self.adapter().test()
        self.assertTrue(ok["ok"], ok)
        self.assertIn("127.0.0.1", ok["detail"])
        self.assertEqual(fs.requests_log(self.port)[-1]["query"], {"limit": "1"})
        bad = self.adapter(key="sk-ant-wrong-AAAABBBBCCCC1234").test()
        self.assertFalse(bad["ok"])
        self.assertNotIn("AAAABBBBCCCC", str(bad))
