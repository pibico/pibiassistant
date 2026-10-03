"""Provider error model: mapping, scrubbing and user messages."""

import pickle
import unittest
from unittest import mock

from pibiassistant.pibiassistant_chat.api.chat.providers import errors, get_provider, http, provider_def


class TestErrorMapping(unittest.TestCase):
    def _kind(self, status, body=None, headers=None):
        return http.error_from_body(status, body or {}, headers or {}).kind

    def test_status_mapping(self):
        cases = {401: "auth", 403: "auth", 402: "quota", 429: "rate_limit", 529: "overloaded", 503: "overloaded",
                 404: "not_found", 400: "invalid_request", 413: "invalid_request", 422: "invalid_request",
                 408: "timeout", 504: "timeout", 500: "server", 502: "server"}
        for status, kind in cases.items():
            self.assertEqual(self._kind(status), kind, status)

    def test_code_mapping(self):
        self.assertEqual(self._kind(429, {"error": {"code": "insufficient_quota", "message": "x"}}), "quota")
        self.assertEqual(self._kind(400, {"type": "error", "error": {"type": "billing_error", "message": "x"}}), "quota")
        self.assertEqual(self._kind(200, {"type": "error", "error": {"type": "overloaded_error", "message": "x"}}), "overloaded")
        self.assertEqual(self._kind(400, {"error": {"code": "content_filter", "message": "x"}}), "content_filter")
        self.assertEqual(self._kind(400, {"error": {"code": "content_policy_violation", "message": "x"}}), "content_filter")

    def test_safe_message_scrubbed_and_clipped(self):
        body = {"error": {"message": "bad key sk-abcdefghijkl1234 and Bearer abc.def " + "x" * 400}}
        e = http.error_from_body(401, body, {"x-request-id": "req_1"})
        self.assertNotIn("sk-abcdefghijkl1234", e.safe_message)
        self.assertNotIn("abc.def", e.safe_message)
        self.assertLessEqual(len(e.safe_message), 300)
        self.assertEqual(e.request_id, "req_1")

    def test_non_json_body_gives_empty_message(self):
        self.assertEqual(http.error_from_body(500, {}).safe_message, "")

    def test_retry_after_parsed(self):
        self.assertEqual(http.error_from_body(429, {}, {"retry-after": "3"}).retry_after, 3.0)
        self.assertIsNone(http.error_from_body(429, {}, {"retry-after": "soon"}).retry_after)


class TestScrub(unittest.TestCase):
    def test_patterns(self):
        for secret in ("sk-ABCDEFGH12345", "tok.en-123", "hello123", "A" * 40, "pass"):
            for fmt in ("fail {}", "Bearer {}", "api_key={}", "api-key: {}", "https://user:{}@host.example/x"):
                if secret in ("tok.en-123",) and not fmt.startswith("Bearer"):
                    continue
                if secret == "hello123" and "api" not in fmt:
                    continue
                if secret == "pass" and "user:" not in fmt:
                    continue
                if secret in ("sk-ABCDEFGH12345", "A" * 40) and "user:" in fmt:
                    continue
                self.assertNotIn(secret, errors.scrub(fmt.format(secret)), fmt)

    def test_configured_key_removed(self):
        self.assertEqual(errors.scrub("a zz9k b", key="zz9k"), "a *** b")


class TestUserMessages(unittest.TestCase):
    def test_all_kinds_are_text_with_label(self):
        for cls in (errors.ProviderAuthError, errors.ProviderQuotaError, errors.ProviderRateLimitError,
                    errors.ProviderOverloadedError, errors.ProviderNotFoundError, errors.ProviderContentFilterError,
                    errors.ProviderTimeoutError, errors.ProviderNetworkError, errors.ProviderServerError):
            msg = cls(label="Acme").user_message()
            self.assertIn("Acme", msg, cls)

    def test_detail_variants(self):
        self.assertIn("boom", errors.ProviderInvalidRequestError("boom", label="Acme").user_message())
        plain = errors.ProviderInvalidRequestError(label="Acme").user_message()
        self.assertIn("Acme", plain)
        self.assertNotIn("None", plain)
        self.assertIn("tools", errors.ProviderUnsupportedError("", feature="tools", label="A").user_message())
        self.assertIn("detail", errors.ProviderConfigError("detail", label="A").user_message())

    def test_str_and_kinds(self):
        self.assertEqual(str(errors.ProviderAuthError()), "auth")
        self.assertEqual(str(errors.ProviderServerError("why")), "why")
        self.assertEqual(errors.ProviderCancelled().kind, "cancelled")
        self.assertIsInstance(errors.ProviderQuotaError(), errors.ProviderError)

    def test_log_provider_error_has_no_provider_text(self):
        e = errors.ProviderServerError("secret detail", status=500, request_id="r1", provider="openai")
        with mock.patch.object(errors.frappe, "log_error") as log:
            errors.log_provider_error(e)
        kw = log.call_args.kwargs
        self.assertEqual(kw["title"], "LLM Provider Error")
        self.assertNotIn("secret detail", kw["message"])
        self.assertIn("r1", kw["message"])


class TestAdapterSecrecy(unittest.TestCase):
    def test_repr_and_pickle_hide_key(self):
        a = get_provider({"provider_id": "openai", "slug": "openai", "name": "x"}, key="sk-test-SECRETKEY1")
        self.assertNotIn("SECRETKEY1", repr(a))
        self.assertNotIn("SECRETKEY1", str(a.__dict__.get("row")))
        with self.assertRaises(TypeError):
            pickle.dumps(a)

    def test_unknown_provider(self):
        with self.assertRaises(errors.ProviderConfigError):
            get_provider({"provider_id": "nope"})
        with self.assertRaises(errors.ProviderConfigError):
            provider_def("nope")


class TestRegistry(unittest.TestCase):
    def test_catalog_is_json_safe_and_complete(self):
        import json

        from pibiassistant.pibiassistant_chat.api.chat.providers import PROVIDER_DEFS, public_catalog

        cat = public_catalog()
        json.dumps(cat)
        self.assertEqual({c["id"] for c in cat}, set(PROVIDER_DEFS))
        self.assertEqual(set(PROVIDER_DEFS), {"openai", "anthropic", "deepseek", "qwen", "xai", "azure_openai", "openai_compatible"})
        qwen = next(c for c in cat if c["id"] == "qwen")
        self.assertEqual(len(qwen["presets"]), 2)
        self.assertTrue(next(c for c in cat if c["id"] == "azure_openai")["base_url_required"])
        self.assertFalse(next(c for c in cat if c["id"] == "openai_compatible")["key_required"])

    def test_model_filters(self):
        from pibiassistant.pibiassistant_chat.api.chat.providers.registry import filter_models, provider_def

        ids = ["gpt-5-mini", "o3", "chatgpt-4o-latest", "text-embedding-3-small", "whisper-1", "gpt-image-1", "gpt-4o-realtime-preview", "davinci-002"]
        out = [m["id"] for m in filter_models(provider_def("openai"), [{"id": i} for i in ids])]
        self.assertEqual(out, ["gpt-5-mini", "o3", "chatgpt-4o-latest"])
