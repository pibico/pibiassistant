"""OpenAI-family adapters against the local fake server."""

import pickle
import time
from unittest import mock

from pibiassistant.pibiassistant_chat.api.chat.providers import (
    ProviderAuthError,
    ProviderCancelled,
    ProviderConfigError,
    ProviderInvalidRequestError,
    ProviderNotFoundError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderUnsupportedError,
    get_provider,
)
from pibiassistant.pibiassistant_chat.api.chat.providers.openai_compat import OpenAICompatAdapter, ThinkStripper
from pibiassistant.tests import _fakeserver as fs

KEY = fs.FAKE_KEY
HELLO = [{"role": "user", "content": "hola"}]
TOOLS = [{"type": "function", "function": {"name": "get_doctype_info", "description": "d",
                                           "parameters": {"type": "object", "properties": {"doctype": {"type": "string"}}}}},
         {"type": "function", "function": {"name": "other", "description": "d", "parameters": {"type": "object", "properties": {}}}}]


class OpenAICase(fs.ServerCase):
    KIND = "openai"

    def adapter(self, provider_id="openai", model="echo-1", key=KEY, **kw):
        return get_provider(self.row(provider_id, model, **kw), key=key)

    def body(self, i=-1):
        return self.posts()[i]["body"]


class TestChat(OpenAICase):
    def test_plain_chat(self):
        res = self.adapter().chat(HELLO)
        self.assertEqual(res["content"], "ECO: hola")
        self.assertEqual(res["model"], "echo-1")
        self.assertEqual(res["finish_reason"], "stop")
        self.assertEqual(res["tool_calls"], [])
        self.assertGreater(res["usage"]["prompt_tokens"], 0)
        self.assertGreater(res["usage"]["completion_tokens"], 0)
        rec = self.posts()[0]
        self.assertTrue(rec["auth_ok"])
        self.assertEqual(rec["path"], "/v1/chat/completions")
        for banned in ("temperature", "top_p", "frequency_penalty", "presence_penalty", "tool_choice"):
            self.assertNotIn(banned, rec["body"])

    def test_tool_call_and_result_round_trip(self):
        a = self.adapter()
        msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "usa la herramienta"}]
        res = a.chat(msgs, tools=TOOLS)
        self.assertEqual(res["finish_reason"], "tool_calls")
        self.assertEqual(res["tool_calls"], [{"name": "get_doctype_info", "arguments": {"doctype": "User"}}])
        msgs += [{"role": "assistant", "content": "", "tool_calls": [{"function": res["tool_calls"][0]["name"] and {"name": "get_doctype_info", "arguments": {"doctype": "User"}}}]},
                 {"role": "tool", "tool_name": "get_doctype_info", "content": "campos de User"}]
        res2 = a.chat(msgs, tools=TOOLS)
        self.assertEqual(res2["content"], "RESULTADO: campos de User")
        sent = self.body()["messages"]
        asst = next(m for m in sent if m.get("tool_calls"))
        tmsg = next(m for m in sent if m["role"] == "tool")
        self.assertEqual(tmsg["tool_call_id"], asst["tool_calls"][0]["id"])
        self.assertIsInstance(asst["tool_calls"][0]["function"]["arguments"], str)

    def test_several_tool_calls_in_one_turn(self):
        a = self.adapter()
        msgs = [{"role": "user", "content": "multiherramienta"}]
        res = a.chat(msgs, tools=TOOLS)
        self.assertEqual(len(res["tool_calls"]), 2)
        msgs.append({"role": "assistant", "content": "", "tool_calls": [{"function": c} for c in res["tool_calls"]]})
        msgs += [{"role": "tool", "tool_name": "get_doctype_info", "content": "R1"}, {"role": "tool", "tool_name": "other", "content": "R2"}]
        self.assertEqual(a.chat(msgs, tools=TOOLS)["content"], "RESULTADO: R1 | R2")
        sent = self.body()["messages"]
        ids = [c["id"] for c in sent[1]["tool_calls"]]
        self.assertEqual([m["tool_call_id"] for m in sent[2:4]], ids)

    def test_tools_empty_list_is_no_tools(self):
        self.adapter().chat(HELLO, tools=[])
        self.assertNotIn("tools", self.body())

    def test_model_defaults_and_missing(self):
        self.assertEqual(self.adapter(model="echo-9").chat(HELLO)["model"], "echo-9")
        with self.assertRaises(ProviderConfigError):
            self.adapter(model="").chat(HELLO)

    def test_missing_key_is_config_error_and_no_request(self):
        with self.assertRaises(ProviderConfigError):
            self.adapter(key="").chat(HELLO)
        self.assertEqual(self.posts(), [])

    def test_key_fetched_lazily_at_call_time(self):
        from pibiassistant.pibiassistant_chat.api import llm_config

        with mock.patch.object(llm_config, "get_provider_key", return_value=KEY, create=True) as g:
            a = get_provider(self.row("openai"))
            g.assert_not_called()
            self.assertEqual(a.chat(HELLO)["content"], "ECO: hola")
            g.assert_called_with("ZZ-row")

    def test_max_tokens_params(self):
        self.adapter(model="gpt-5-mini").chat(HELLO)
        b = self.body()
        self.assertGreaterEqual(b["max_completion_tokens"], 8192)
        self.assertNotIn("max_tokens", b)
        self.adapter(model="echo-1").chat(HELLO, max_tokens=123)
        b = self.body()
        self.assertEqual(b["max_tokens"], 123)
        self.assertNotIn("max_completion_tokens", b)
        self.adapter(model="echo-1", max_output_tokens=777).chat(HELLO)
        self.assertEqual(self.body()["max_tokens"], 777)

    def test_token_param_swap_on_400(self):
        self.adapter(model="reject-max-tokens").chat(HELLO)
        posts = self.posts()
        self.assertEqual(len(posts), 2)
        self.assertIn("max_tokens", posts[0]["body"])
        self.assertIn("max_completion_tokens", posts[1]["body"])
        self.assertNotIn("max_tokens", posts[1]["body"])

    def test_reasoning_effort_none_sent_with_tools_for_gpt_5_4_plus(self):
        self.adapter(model="gpt-5.6-test").chat([{"role": "user", "content": "x"}], tools=TOOLS)
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(self.body()["reasoning_effort"], "none")
        fs.reset(self.port)
        self.adapter(model="gpt-5.6-test").chat(HELLO)
        self.assertNotIn("reasoning_effort", self.body())

    def test_reasoning_effort_retry_after_400(self):
        res = self.adapter(model="gpt-5.3-test").chat([{"role": "user", "content": "x"}], tools=TOOLS)
        self.assertEqual(res["finish_reason"], "stop")
        posts = self.posts()
        self.assertEqual(len(posts), 2)
        self.assertNotIn("reasoning_effort", posts[0]["body"])
        self.assertEqual(posts[1]["body"]["reasoning_effort"], "none")

    def test_empty_content_with_length_explains_reasoning_budget(self):
        with self.assertRaises(ProviderInvalidRequestError) as cm:
            self.adapter(model="empty-length").chat(HELLO)
        self.assertIn("Output budget used by reasoning", str(cm.exception))

    def test_unknown_kwargs_ignored(self):
        self.assertEqual(self.adapter().chat(HELLO, _thinking_disabled=True)["content"], "ECO: hola")


class TestErrorsAndRetries(OpenAICase):
    def test_429_then_success_is_retried(self):
        res = self.adapter(model="flaky-429").chat(HELLO)
        self.assertEqual(res["content"], "ECO: hola")
        self.assertEqual(len(self.posts()), 2)

    def test_429_gives_up_after_three_attempts(self):
        with self.assertRaises(ProviderRateLimitError) as cm:
            self.adapter(model="fail-429").chat(HELLO)
        self.assertEqual(len(self.posts()), 3)
        self.assertEqual(cm.exception.retry_after, 0.0)

    def test_500_retried_then_server_error(self):
        with self.assertRaises(ProviderServerError):
            self.adapter(model="fail-500").chat(HELLO)
        self.assertEqual(len(self.posts()), 3)

    def test_retry_after_is_honoured_and_capped(self):
        from pibiassistant.pibiassistant_chat.api.chat.providers import http

        slept = []
        with mock.patch.object(http, "_sleep", lambda s, c, r: slept.append(s)):
            with mock.patch.object(http, "RETRY_DELAYS", (1.0, 2.0)):
                with self.assertRaises(ProviderRateLimitError):
                    self.adapter(model="fail-429").chat(HELLO)
        self.assertEqual(slept, [0.0, 0.0])  # Retry-After: 0 wins over the default backoff

    def test_no_retry_for_quota_auth_and_400(self):
        with self.assertRaises(ProviderQuotaError):
            self.adapter(model="quota-429").chat(HELLO)
        self.assertEqual(len(self.posts()), 1)
        fs.reset(self.port)
        with self.assertRaises(ProviderAuthError):
            self.adapter(model="fail-401").chat(HELLO)
        self.assertEqual(len(self.posts()), 1)
        fs.reset(self.port)
        with self.assertRaises(ProviderInvalidRequestError):
            self.adapter(model="fail-400-tools").chat(HELLO, tools=TOOLS)
        self.assertEqual(len(self.posts()), 1)

    def test_deepseek_402_is_quota(self):
        with self.assertRaises(ProviderQuotaError):
            self.adapter("deepseek", "fail-402").chat(HELLO)

    def test_not_found_for_unknown_path(self):
        with self.assertRaises(ProviderNotFoundError):
            self.adapter(base_url=f"http://127.0.0.1:{self.port}/nope").chat(HELLO)

    def test_wrong_key_never_in_errors(self):
        wrong = "sk-wrong-AAAABBBBCCCC1234"
        a = self.adapter(key=wrong)
        with self.assertRaises(ProviderAuthError) as cm:
            a.chat(HELLO)
        e = cm.exception
        for text in (str(e), e.safe_message, e.user_message(), repr(e), repr(a)):
            self.assertNotIn("AAAABBBBCCCC", text)
        with self.assertRaises(TypeError):
            pickle.dumps(a)

    def test_read_timeout_maps_to_timeout_error(self):
        with mock.patch.object(OpenAICompatAdapter, "_timeout", return_value=(2, 1)):
            t0 = time.time()
            with self.assertRaises(ProviderTimeoutError):
                self.adapter(model="slow").chat(HELLO)
        self.assertLess(time.time() - t0, 6)
        self.assertEqual(len(self.posts()), 1)

    def test_connection_refused_is_network_error_after_retries(self):
        from pibiassistant.pibiassistant_chat.api.chat.providers import ProviderNetworkError

        with self.assertRaises(ProviderNetworkError):
            self.adapter(base_url="http://127.0.0.1:1/v1").chat(HELLO)

    def test_cancel_before_call_and_between_retries(self):
        with self.assertRaises(ProviderCancelled):
            self.adapter().chat(HELLO, cancel=lambda: True)
        self.assertEqual(self.posts(), [])
        state = {"n": 0}

        def cancel():
            state["n"] += 1
            return state["n"] > 1

        with self.assertRaises(ProviderCancelled):
            self.adapter(model="fail-429").chat(HELLO, cancel=cancel)
        self.assertEqual(len(self.posts()), 1)


class TestStream(OpenAICase):
    def run_stream(self, a, msgs=HELLO, **kw):
        return list(a.stream_chat(msgs, **kw))

    def test_stream_chunks_and_usage(self):
        ev = self.run_stream(self.adapter())
        self.assertEqual("".join(e["content"] for e in ev if e["type"] == "chunk"), "ECO: hola")
        self.assertEqual(ev[-1]["type"], "done")
        self.assertGreater(ev[-1]["usage"]["prompt_tokens"], 0)
        self.assertGreater(ev[-1]["usage"]["completion_tokens"], 0)
        self.assertEqual(ev[-1]["finish_reason"], "stop")
        self.assertEqual(sum(1 for e in ev if e["type"] in ("done", "error", "cancelled")), 1)
        b = self.body()
        self.assertTrue(b["stream"])
        self.assertTrue(b["stream_options"]["include_usage"])

    def test_tool_fragments_accumulate_in_done(self):
        ev = self.run_stream(self.adapter(), [{"role": "user", "content": "multiherramienta"}], tools=TOOLS)
        self.assertFalse([e for e in ev if e["type"] == "chunk"])
        done = ev[-1]
        self.assertEqual(done["finish_reason"], "tool_calls")
        self.assertEqual(done["tool_calls"], [{"name": "get_doctype_info", "arguments": {"doctype": "User"}},
                                              {"name": "other", "arguments": {}}])

    def test_stream_options_rejected_retries_without(self):
        ev = self.run_stream(self.adapter(model="reject-stream-options"))
        self.assertEqual(ev[-1]["type"], "done")
        self.assertEqual(ev[-1]["usage"], {"prompt_tokens": 0, "completion_tokens": 0})
        self.assertEqual(len(self.posts()), 2)
        self.assertNotIn("stream_options", self.body())

    def test_failures_before_first_event_raise(self):
        with self.assertRaises(ProviderAuthError):
            self.run_stream(self.adapter(model="fail-401"))
        with self.assertRaises(ProviderRateLimitError):
            self.run_stream(self.adapter(model="fail-429"))

    def test_cancel_before_start(self):
        self.assertEqual(self.run_stream(self.adapter(), cancel=lambda: True), [{"type": "cancelled"}])

    def test_cancel_mid_stream_closes(self):
        seen = {"chunk": False}
        out = []
        t0 = time.time()
        for e in self.adapter(model="slow").stream_chat(HELLO, cancel=lambda: seen["chunk"]):
            out.append(e)
            if e["type"] == "chunk":
                seen["chunk"] = True
        self.assertEqual(out[-1], {"type": "cancelled"})
        self.assertLess(time.time() - t0, 6)


class TestFamily(OpenAICase):
    def test_deepseek_flags(self):
        a = self.adapter("deepseek", "echo-1")
        a.chat(HELLO)
        self.assertEqual(self.body()["thinking"], {"type": "disabled"})
        self.assertEqual(self.body()["max_tokens"], 4096)
        list(a.stream_chat(HELLO))
        self.assertEqual(self.body()["thinking"], {"type": "disabled"})

    def test_qwen_flags_stream_and_non_stream(self):
        a = self.adapter("qwen", "echo-1")
        a.chat(HELLO)
        self.assertIs(self.body()["enable_thinking"], False)
        list(a.stream_chat(HELLO))
        self.assertIs(self.body()["enable_thinking"], False)

    def test_xai_body_and_model_listing(self):
        a = self.adapter("xai", "echo-1")
        a.chat(HELLO, tools=TOOLS)
        b = self.body()
        for k in ("reasoning_effort", "stop", "presence_penalty", "frequency_penalty"):
            self.assertNotIn(k, b)
        self.assertEqual([m["id"] for m in a.list_models()], ["grok-3-mini", "grok-4.5"])
        self.assertEqual(self.posts()[-1]["path"], "/v1/chat/completions")
        self.assertIn("/v1/language-models", [r["path"] for r in fs.requests_log(self.port)])

    def test_xai_models_fallback_when_language_models_missing(self):
        a = self.adapter("xai", "echo-1", base_url=f"http://127.0.0.1:{self.port}/v1")
        with mock.patch.object(type(a), "_models_paths", lambda s: ["/nope", "/models"]):
            ids = [m["id"] for m in a.list_models()]
        self.assertIn("gpt-5-mini", ids)

    def test_model_listing_filters(self):
        self.assertEqual([m["id"] for m in self.adapter("openai").list_models()], ["gpt-5-mini"])
        generic = [m["id"] for m in self.adapter("openai_compatible").list_models()]
        self.assertEqual(generic, ["echo-1", "gpt-5-mini", "or/txt"])
        self.assertTrue(all(set(m) == {"id", "label"} for m in self.adapter("openai_compatible").list_models()))

    def test_generic_tolerances(self):
        a = self.adapter("openai_compatible", "odd-tools")
        res = a.chat([{"role": "user", "content": "herramienta"}], tools=TOOLS)
        self.assertEqual(res["tool_calls"], [{"name": "get_doctype_info", "arguments": {"doctype": "User"}}])
        self.assertEqual(res["usage"], {"prompt_tokens": 0, "completion_tokens": 0})
        self.assertEqual(self.adapter("openai_compatible", "odd-parts").chat(HELLO)["content"], "Hola mundo")
        res = self.adapter("openai_compatible", "odd-think").chat(HELLO)
        self.assertEqual(res["content"], "ECO: hola")
        ev = list(self.adapter("openai_compatible", "odd-think").stream_chat(HELLO))
        self.assertEqual("".join(e.get("content", "") for e in ev), "ECO: hola")

    def test_generic_without_key_sends_no_authorization(self):
        res = self.adapter("openai_compatible", "noauth", key="").chat(HELLO)
        self.assertEqual(res["content"], "ECO: hola")
        self.assertFalse(self.posts()[0]["auth_present"])

    def test_generic_tools_rejected_maps_to_unsupported(self):
        with self.assertRaises(ProviderUnsupportedError) as cm:
            self.adapter("openai_compatible", "fail-400-tools").chat(HELLO, tools=TOOLS)
        self.assertEqual(cm.exception.feature, "tools")

    def test_base_url_with_chat_completions_suffix_is_normalised(self):
        a = self.adapter(base_url=f"http://127.0.0.1:{self.port}/v1/chat/completions")
        self.assertEqual(a.chat(HELLO)["content"], "ECO: hola")
        self.assertEqual(self.posts()[0]["path"], "/v1/chat/completions")

    def test_adapter_test_method(self):
        ok = self.adapter("openai").test()
        self.assertTrue(ok["ok"])
        self.assertIn("127.0.0.1", ok["detail"])
        self.assertIn("1 models", ok["detail"])
        self.assertNotIn(KEY, str(ok))
        bad = self.adapter("openai", key="sk-wrong-AAAABBBBCCCC1234").test()
        self.assertFalse(bad["ok"])
        self.assertTrue(bad["error"])
        self.assertNotIn("AAAABBBBCCCC", str(bad))
        nokey = self.adapter("openai", key="").test()
        self.assertFalse(nokey["ok"])
        self.assertEqual(nokey["models"], [])


class TestAzure(OpenAICase):
    def az(self, **kw):
        row = dict(deployment="echo-1", default_model="", api_version="2025-01-01")
        row.update(kw)
        return self.adapter("azure_openai", "", **row)

    def test_url_header_version_and_body(self):
        res = self.az().chat(HELLO)
        self.assertEqual(res["content"], "ECO: hola")
        rec = self.posts()[0]
        self.assertEqual(rec["path"], "/openai/deployments/echo-1/chat/completions")
        self.assertEqual(rec["query"], {"api-version": "2025-01-01"})
        self.assertTrue(rec["auth_ok"])
        self.assertNotIn("model", rec["body"])
        self.assertIn("max_completion_tokens", rec["body"])
        self.assertNotIn("authorization", rec["headers"])

    def test_default_api_version_and_stream(self):
        a = self.az(api_version="")
        ev = list(a.stream_chat(HELLO))
        self.assertEqual(ev[-1]["type"], "done")
        self.assertEqual(self.posts()[0]["query"], {"api-version": "2024-10-21"})

    def test_deployment_override_and_validation(self):
        self.az().chat(HELLO, model="echo-2")
        self.assertIn("/echo-2/", self.posts()[-1]["path"])
        with self.assertRaises(ProviderConfigError):
            self.az().chat(HELLO, model="../evil")
        for dots in ("..", ".", ".hidden"):
            with self.assertRaises(ProviderConfigError):
                self.az().chat(HELLO, model=dots)
        with self.assertRaises(ProviderConfigError):
            self.adapter("azure_openai", "", deployment="", default_model="").chat(HELLO)

    def test_list_models_needs_no_network(self):
        out = self.az(extra_models=["echo-2", "echo-1"]).list_models()
        self.assertEqual([m["id"] for m in out], ["echo-1", "echo-2"])
        self.assertEqual(fs.requests_log(self.port), [])

    def test_test_sends_small_chat(self):
        res = self.az().test()
        self.assertTrue(res["ok"], res)
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(self.posts()[0]["body"]["messages"][-1]["content"], "Reply with OK")

    def test_wrong_key_401_shape(self):
        with self.assertRaises(ProviderAuthError):
            self.adapter("azure_openai", "", key="wrong-key-123456", deployment="echo-1").chat(HELLO)


class TestThinkStripper(OpenAICase):
    def test_split_tags(self):
        s = ThinkStripper()
        out = "".join(s.feed(p) for p in ("Hi <thi", "nk>secret</th", "ink>\n\nthere <", "b>"))
        out += s.feed("", final=True)
        self.assertEqual(out, "Hi there <b>")
