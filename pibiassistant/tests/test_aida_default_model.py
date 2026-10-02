"""A turn with no model named must still get one, otherwise the tool loop is silently skipped."""

import unittest
from unittest import mock

from pibiassistant.pibiassistant_chat.api import aida

MODELS = {
    "success": True,
    "providers": {
        "ollama": {"available": True, "models": ["qwen3-embedding:8b", "gpt-oss:20b"]},
        "openai": {"available": True, "models": ["gpt-5-mini"]},
        "anthropic": {"available": False, "models": ["claude-sonnet-5"]},
    },
}


class TestDefaultChatModel(unittest.TestCase):
    def _run(self, provider, data=MODELS, config=("https://x", "k", "", "")):
        cache = mock.Mock()
        cache.get_value.return_value = data
        with mock.patch.object(aida, "_get_aida_config", return_value=config), mock.patch.object(
            aida.frappe, "cache", return_value=cache
        ):
            return aida.default_chat_model(provider)

    def test_skips_embedding_models(self):
        self.assertEqual(self._run("ollama"), ("ollama", "gpt-oss:20b"))

    def test_unknown_provider_falls_back_to_first_available(self):
        self.assertEqual(self._run("nope"), ("ollama", "gpt-oss:20b"))

    def test_unavailable_provider_is_skipped(self):
        data = {"providers": {"anthropic": {"available": False, "models": ["c"]}, "openai": {"available": True, "models": ["m"]}}}
        self.assertEqual(self._run("anthropic", data), ("openai", "m"))

    def test_not_configured(self):
        self.assertEqual(self._run("ollama", config=("", "", "", "")), ("", ""))
