"""llm_config: provider reader, backend modes, model ids, listings and missing-schema behaviour."""

import os
import re
from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.pibiassistant_chat.api import llm_config
from pibiassistant.tests.base_test import BaseAssistantTest

MOD = "pibiassistant.pibiassistant_chat.api.llm_config"


def row(slug="openai", provider_id="openai", **kw):
    base = {
        "name": f"zz-row-{slug}",
        "idx": 1,
        "provider_id": provider_id,
        "slug": slug,
        "label": kw.pop("label", slug.title()),
        "enabled": True,
        "base_url": "",
        "default_model": "gpt-x",
        "extra_models": [],
        "api_version": "",
        "deployment": "",
        "timeout_seconds": 120,
        "max_output_tokens": 0,
        "supports_tools": True,
        "has_key": True,
    }
    base.update(kw)
    return base


def mode(value, aida_key=False, rows=None):
    """Patch the three inputs of the mode logic."""
    settings = MagicMock()
    settings.get.side_effect = lambda k, d=None: {
        "llm_backend_mode": value,
        "aida_default_provider": "ollama",
        "aida_default_model": "m1",
    }.get(k, d)
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(patch(f"{MOD}._settings", return_value=settings))
    stack.enter_context(patch("pibiassistant.pibiassistant_chat.aida_mode.is_aida_mode", return_value=aida_key))
    stack.enter_context(patch(f"{MOD}.llm_providers", side_effect=lambda enabled_only=False: [r for r in (rows or []) if r["enabled"] or not enabled_only]))
    return stack


class TestMissingSchema(BaseAssistantTest):
    def test_everything_degrades_when_table_is_missing(self):
        settings = MagicMock()
        settings.get.return_value = None
        with patch("frappe.db.table_exists", return_value=False), patch(f"{MOD}._settings", return_value=settings), patch(
            "pibiassistant.pibiassistant_chat.aida_mode.is_aida_mode", return_value=True
        ):
            self.assertEqual(llm_config.llm_providers(), [])
            self.assertEqual(llm_config.backend_mode(), "aida")
            self.assertTrue(llm_config.mode_allows_aida())
            self.assertFalse(llm_config.mode_allows_direct())
            self.assertIsNone(llm_config.provider_by_slug("openai"))
            self.assertIsNone(llm_config.provider_by_name("x"))
            self.assertEqual(llm_config.usable_providers(), [])
            self.assertTrue(llm_config.llm_ready())
            self.assertEqual(llm_config.default_backend_choice(), ("aida", "", ""))
            self.assertEqual(llm_config.resolve_backend("d:openai/x"), ("aida", "", ""))
            self.assertEqual(llm_config.resolve_backend("ollama/qwen"), ("aida", "ollama", "qwen"))
            self.assertEqual(llm_config.direct_models(), [])
            self.assertEqual(llm_config.refresh_provider_models("nope"), [])
            self.assertIsNone(llm_config.refresh_direct_models())
            self.assertIsNone(llm_config.invalidate_llm_cache())
            self.assertEqual(llm_config.cached_provider_status(), {})

    def test_reader_never_raises(self):
        with patch("frappe.db.table_exists", side_effect=RuntimeError("db down")):
            self.assertEqual(llm_config.llm_providers(), [])
        with patch("frappe.db.table_exists", return_value=True), patch("frappe.get_all", side_effect=Exception("Unknown column")):
            frappe.cache().delete_value("pa_llm_providers")
            self.assertEqual(llm_config.llm_providers(), [])

    def test_mode_aida_does_not_read_providers(self):
        with mode("AIDA only", aida_key=True), patch(f"{MOD}.llm_providers") as reader:
            self.assertTrue(llm_config.llm_ready())
            self.assertFalse(llm_config.mode_allows_direct())
            reader.assert_not_called()

    def test_unknown_mode_value_is_aida(self):
        with mode("Whatever"):
            self.assertEqual(llm_config.backend_mode(), "aida")


class TestReader(BaseAssistantTest):
    def test_labels_made_unique_and_slug_fallback(self):
        raw = [
            {"name": "a", "idx": 1, "provider_id": "openai_compatible", "slug": "", "label": "Proxy", "enabled": 1,
             "base_url": "https://x", "default_model": "m", "extra_models": "a\n b \n", "api_version": "",
             "deployment": "", "timeout_seconds": None, "max_output_tokens": 0, "supports_tools": 1},
            {"name": "b", "idx": 2, "provider_id": "openai_compatible", "slug": "openai-compatible-2", "label": "Proxy",
             "enabled": 0, "base_url": "", "default_model": "", "extra_models": "", "api_version": "",
             "deployment": "", "timeout_seconds": 30, "max_output_tokens": 0, "supports_tools": 0},
        ]
        with patch("frappe.db.table_exists", return_value=True), patch("frappe.get_all", return_value=raw), patch(
            f"{MOD}._keyed_names", return_value={"a"}
        ):
            frappe.cache().delete_value("pa_llm_providers")
            try:
                rows = llm_config.llm_providers()
                self.assertEqual([r["slug"] for r in rows], ["openai-compatible", "openai-compatible-2"])
                self.assertEqual(rows[0]["label"], "Proxy (openai-compatible)")
                self.assertEqual(rows[0]["extra_models"], ["a", "b"])
                self.assertEqual(rows[0]["timeout_seconds"], 120)
                self.assertTrue(rows[0]["has_key"])
                self.assertFalse(rows[1]["has_key"])
                self.assertEqual([r["name"] for r in llm_config.llm_providers(enabled_only=True)], ["a"])
                self.assertNotIn("api_key", rows[0])
            finally:
                frappe.cache().delete_value("pa_llm_providers")


class TestModelIds(BaseAssistantTest):
    def test_parse_model_id(self):
        p = llm_config.parse_model_id
        self.assertEqual(p(None), ("auto", "", ""))
        self.assertEqual(p(""), ("auto", "", ""))
        self.assertEqual(p(" auto "), ("auto", "", ""))
        self.assertEqual(p("d:openai/gpt-5-mini"), ("direct", "openai", "gpt-5-mini"))
        self.assertEqual(p("d:openrouter/meta/llama-3"), ("direct", "openrouter", "meta/llama-3"))
        self.assertEqual(p("d:openai"), ("auto", "", ""))
        self.assertEqual(p("d:/x"), ("auto", "", ""))
        self.assertEqual(p("d:x/"), ("auto", "", ""))
        self.assertEqual(p("openai/gpt-x"), ("aida", "openai", "gpt-x"))
        self.assertEqual(p("a/b/c"), ("aida", "a", "b/c"))
        self.assertEqual(p("llama3"), ("aida", "", "llama3"))
        self.assertEqual(len(p("x" * 500)[2]), 200)


class TestResolve(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.rows = [row("openai"), row("anthropic", "anthropic", default_model="")]

    def test_aida_mode_ignores_direct_ids(self):
        with mode("AIDA only", aida_key=True, rows=self.rows):
            self.assertEqual(llm_config.resolve_backend("d:openai/gpt-x"), ("aida", "ollama", "m1"))
            self.assertEqual(llm_config.resolve_backend("openai/gpt-x"), ("aida", "openai", "gpt-x"))
            self.assertEqual(llm_config.resolve_backend("auto"), ("aida", "ollama", "m1"))

    def test_direct_mode(self):
        with mode("Direct providers", aida_key=True, rows=self.rows):
            self.assertEqual(llm_config.resolve_backend("d:openai/gpt-y"), ("direct", "openai", "gpt-y"))
            self.assertEqual(llm_config.resolve_backend("auto"), ("direct", "openai", "gpt-x"))
            # an AIDA id is ignored in direct mode
            self.assertEqual(llm_config.resolve_backend("openai/gpt-x"), ("direct", "openai", "gpt-x"))
            self.assertEqual(llm_config.resolve_backend("d:missing/x"), ("direct", "openai", "gpt-x"))
            # empty model falls back to the row default
            self.assertEqual(llm_config.resolve_backend("d:openai/"), ("direct", "openai", "gpt-x"))

    def test_both_mode(self):
        with mode("Both", aida_key=True, rows=self.rows):
            self.assertEqual(llm_config.resolve_backend("auto"), ("aida", "ollama", "m1"))
            self.assertEqual(llm_config.resolve_backend("d:openai/gpt-y"), ("direct", "openai", "gpt-y"))
            self.assertEqual(llm_config.resolve_backend("openai/gpt-x"), ("aida", "openai", "gpt-x"))
        with mode("Both", aida_key=False, rows=self.rows):
            self.assertEqual(llm_config.resolve_backend("auto"), ("direct", "openai", "gpt-x"))
            self.assertEqual(llm_config.resolve_backend("openai/gpt-x"), ("direct", "openai", "gpt-x"))

    def test_disabled_or_unusable_row_falls_back(self):
        rows = [row("openai", enabled=False), row("anthropic", "anthropic", has_key=False)]
        with mode("Both", aida_key=True, rows=rows):
            self.assertEqual(llm_config.resolve_backend("d:openai/x"), ("aida", "ollama", "m1"))
            self.assertEqual(llm_config.resolve_backend("d:anthropic/x"), ("aida", "ollama", "m1"))
        with mode("Direct providers", aida_key=True, rows=rows):
            self.assertEqual(llm_config.resolve_backend("auto"), ("none", "", ""))

    def test_no_model_anywhere_is_none(self):
        with mode("Direct providers", rows=[row("openai", default_model="")]):
            self.assertEqual(llm_config.default_backend_choice(), ("direct", "openai", ""))
            self.assertEqual(llm_config.resolve_backend("auto"), ("none", "", ""))
            self.assertEqual(llm_config.resolve_backend("d:openai/"), ("none", "", ""))

    def test_default_direct_model(self):
        self.assertEqual(llm_config.default_direct_model(row(default_model="", deployment="dep")), "dep")
        self.assertEqual(llm_config.default_direct_model(row(default_model="", extra_models=["e1"])), "e1")
        self.assertEqual(llm_config.default_direct_model(row(default_model="", extra_models=[])), "")

    def test_llm_ready_per_mode(self):
        usable = [row("openai")]
        with mode("AIDA only", aida_key=False, rows=usable):
            self.assertFalse(llm_config.llm_ready())
        with mode("AIDA only", aida_key=True, rows=[]):
            self.assertTrue(llm_config.llm_ready())
        with mode("Direct providers", aida_key=True, rows=[]):
            self.assertFalse(llm_config.llm_ready())
        with mode("Direct providers", aida_key=False, rows=usable):
            self.assertTrue(llm_config.llm_ready())
        with mode("Both", aida_key=False, rows=usable):
            self.assertTrue(llm_config.llm_ready())
        with mode("Both", aida_key=True, rows=[]):
            self.assertTrue(llm_config.llm_ready())
        with mode("Both", aida_key=False, rows=[]):
            self.assertFalse(llm_config.llm_ready())

    def test_provider_usable_rules(self):
        self.assertTrue(llm_config.provider_usable(row()))
        self.assertFalse(llm_config.provider_usable(row(has_key=False)))
        self.assertFalse(llm_config.provider_usable(row(enabled=False)))
        compat = row("c", "openai_compatible", has_key=False, base_url="https://x.example")
        self.assertTrue(llm_config.provider_usable(compat))
        self.assertFalse(llm_config.provider_usable(row("c", "openai_compatible", has_key=False)))
        az = row("az", "azure_openai", base_url="https://r.openai.azure.com", deployment="d")
        self.assertTrue(llm_config.provider_usable(az))
        self.assertFalse(llm_config.provider_usable(row("az", "azure_openai", base_url="https://r.openai.azure.com")))
        self.assertFalse(llm_config.provider_usable(row("az", "azure_openai", deployment="d")))


class TestListings(BaseAssistantTest):
    def tearDown(self):
        for n in ("zz-row-openai", "zz-row-anthropic"):
            for k in ("pa_llm_models", "pa_llm_models_stale", "pa_llm_health"):
                frappe.cache().delete_value(f"{k}:{n}")
        super().tearDown()

    def test_provider_models_order_and_cache(self):
        r = row(default_model="a", deployment="b", extra_models=["c", "a"])
        frappe.cache().set_value("pa_llm_models:zz-row-openai", [{"id": "d", "label": "D"}, {"id": "a", "label": "A"}], expires_in_sec=60)
        out = llm_config.provider_models(r)
        self.assertEqual([m["id"] for m in out], ["a", "b", "c", "d"])
        self.assertEqual(out[0]["label"], "A")

    def test_direct_models_entries_and_enqueue(self):
        rows = [row("openai", label="OpenAI", extra_models=["m2"])]
        with mode("Direct providers", rows=rows), patch("frappe.enqueue") as enq:
            entries = llm_config.direct_models()
            self.assertEqual([e["model_id"] for e in entries], ["d:openai/gpt-x", "d:openai/m2"])
            e = entries[0]
            self.assertEqual(e["provider"], "OpenAI (direct)")
            self.assertEqual((e["backend"], e["tier"], e["tier_rank"], e["display_name"]), ("direct", "Standard", 1, "gpt-x"))
            enq.assert_called_once()
            self.assertEqual(enq.call_args.kwargs["queue"], "short")
            self.assertTrue(enq.call_args.kwargs["deduplicate"])

    def test_direct_models_cached_does_not_enqueue(self):
        rows = [row("openai")]
        frappe.cache().set_value("pa_llm_models:zz-row-openai", [], expires_in_sec=60)
        with mode("Both", rows=rows), patch("frappe.enqueue") as enq:
            self.assertEqual(len(llm_config.direct_models()), 1)
            enq.assert_not_called()

    def test_direct_models_refresh_lists_synchronously(self):
        rows = [row("openai")]
        with mode("Both", rows=rows), patch(f"{MOD}.refresh_provider_models", side_effect=RuntimeError("down")) as ref, patch(
            "frappe.enqueue"
        ) as enq:
            self.assertEqual(len(llm_config.direct_models(refresh=True)), 1)
            ref.assert_called_once()
            enq.assert_not_called()

    def test_refresh_provider_models_filters_and_caches(self):
        rows = [row("openai")]
        adapter = MagicMock()
        adapter.list_models.return_value = [{"id": "gpt-5", "label": "gpt-5"}, {"id": "whisper-1", "label": "w"}]
        with mode("Both", rows=rows), patch(
            "pibiassistant.pibiassistant_chat.api.chat.providers.get_provider", return_value=adapter, create=True
        ):
            out = llm_config.refresh_provider_models("zz-row-openai")
        self.assertEqual([m["id"] for m in out], ["gpt-5"])
        self.assertEqual(frappe.cache().get_value("pa_llm_models:zz-row-openai", expires=True), out)
        self.assertEqual(frappe.cache().get_value("pa_llm_models_stale:zz-row-openai", expires=True), out)

    def test_invalidate_drops_keys(self):
        frappe.cache().set_value("pa_llm_providers", [{"name": "zz-row-openai"}], expires_in_sec=60)
        frappe.cache().set_value("pa_llm_models:zz-row-openai", [], expires_in_sec=60)
        frappe.cache().set_value("pa_llm_health:zz-row-openai", {"ok": True}, expires_in_sec=60)
        llm_config.invalidate_llm_cache()
        for k in ("pa_llm_providers", "pa_llm_models:zz-row-openai", "pa_llm_health:zz-row-openai"):
            self.assertIsNone(frappe.cache().get_value(k, expires=True))

    def test_cached_provider_status_keys_look_like_label_api(self):
        rows = [row("openai", label="OpenAI")]
        frappe.cache().set_value("pa_llm_health:zz-row-openai", {"ok": True}, expires_in_sec=60)
        with mode("Both", rows=rows):
            self.assertEqual(llm_config.cached_provider_status(), {"OpenAI API": {"ok": True}})


class TestKeyAccessStatic(BaseAssistantTest):
    def test_only_providers_and_llm_config_read_provider_keys(self):
        import pibiassistant

        root = os.path.dirname(pibiassistant.__file__)
        allowed = {os.path.join(root, "pibiassistant_chat", "api", "llm_config.py")}
        bad = []
        for dp, _dn, fn in os.walk(root):
            if "node_modules" in dp or "/tests" in dp or "/public" in dp or "/providers" in dp:
                continue
            for f in fn:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(dp, f)
                if path in allowed:
                    continue
                text = open(path, encoding="utf-8").read()
                if "get_provider_key" in text or re.search(r"get_decrypted_password\([^)]*PA LLM Provider", text):
                    bad.append(path)
        self.assertEqual(bad, [])

    def test_debug_bundle_does_not_serialise_providers(self):
        import pibiassistant

        path = os.path.join(os.path.dirname(pibiassistant.__file__), "pibiassistant_chat", "api", "chat", "debug_bundle.py")
        self.assertNotIn("llm_providers", open(path, encoding="utf-8").read())
