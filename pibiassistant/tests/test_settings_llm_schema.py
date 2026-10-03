"""Schema, controller rules and admin endpoints of the direct providers settings."""

import json
import os
import re
import unittest
from unittest import mock

import frappe

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DT = os.path.join(BASE, "pibiassistant_core", "doctype")


def _json(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return json.load(f)


class TestSchemaFiles(unittest.TestCase):
    def test_child_doctype_fields_in_contract_order(self):
        d = _json(DT, "pa_llm_provider", "pa_llm_provider.json")
        self.assertEqual(d["name"], "PA LLM Provider")
        self.assertEqual(d["istable"], 1)
        self.assertEqual(d["editable_grid"], 1)
        self.assertEqual(d["module"], "pibiAssistant Core")
        self.assertEqual(
            d["field_order"],
            ["provider_id", "slug", "label", "enabled", "column_break_a", "api_key", "base_url",
             "section_models", "default_model", "deployment", "api_version", "column_break_b",
             "extra_models", "section_limits", "timeout_seconds", "max_output_tokens", "supports_tools",
             "column_break_c", "test_connection", "load_models"],
        )
        self.assertEqual([f["fieldname"] for f in d["fields"]], d["field_order"])
        by = {f["fieldname"]: f for f in d["fields"]}
        self.assertEqual(by["api_key"]["fieldtype"], "Password")
        self.assertEqual(by["slug"]["hidden"], 1)
        self.assertEqual(
            by["provider_id"]["options"].split("\n"),
            ["openai", "anthropic", "deepseek", "qwen", "xai", "azure_openai", "openai_compatible"],
        )
        in_list = {f["fieldname"] for f in d["fields"] if f.get("in_list_view")}
        self.assertEqual(in_list, {"provider_id", "label", "enabled", "default_model"})
        self.assertNotIn("permissions", {k for k, v in d.items() if v})

    def test_settings_fields_follow_voice_key(self):
        d = _json(DT, "pa_core_settings", "pa_core_settings.json")
        order = d["field_order"]
        i = order.index("aida_voice_api_key")
        self.assertEqual(
            order[i + 1:i + 5],
            ["llm_providers_section", "llm_backend_mode", "llm_providers_help", "llm_providers"],
        )
        self.assertEqual(order[i + 5], "plugins_tab")
        by = {f["fieldname"]: f for f in d["fields"]}
        self.assertEqual(by["llm_backend_mode"]["options"], "AIDA only\nDirect providers\nBoth")
        self.assertEqual(by["llm_backend_mode"]["default"], "AIDA only")
        self.assertEqual(by["llm_providers"]["options"], "PA LLM Provider")
        self.assertEqual({f["fieldname"] for f in d["fields"]}, set(order))

    def test_privilege_doctype(self):
        from pibiassistant.core.security_config import PRIVILEGE_DOCTYPES

        self.assertIn("PA LLM Provider", PRIVILEGE_DOCTYPES)

    def test_chat_write_tools_cannot_touch_provider_fields(self):
        from pibiassistant.plugins.core.field_guard import privileged_fields_attempted

        got = privileged_fields_attempted("PA Core Settings", ["llm_providers", "llm_backend_mode", "aida_default_model"])
        self.assertEqual(got, ["llm_providers", "llm_backend_mode"])

    def test_no_key_material_in_form_js(self):
        with open(os.path.join(DT, "pa_core_settings", "pa_core_settings.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertNotIn("get_decrypted_password", js)
        self.assertNotIn("api_key:", js)


class TestControllerRules(unittest.TestCase):
    def setUp(self):
        from pibiassistant.pibiassistant_core.doctype.pa_core_settings import pa_core_settings as m

        self.m = m
        self._conf = frappe.conf.get("pa_allow_private_llm_urls")
        frappe.conf.pop("pa_allow_private_llm_urls", None)

    def tearDown(self):
        if self._conf is None:
            frappe.conf.pop("pa_allow_private_llm_urls", None)
        else:
            frappe.conf.pa_allow_private_llm_urls = self._conf

    def row(self, **kw):
        base = dict(idx=1, name="r1", provider_id="openai", slug="", label="", enabled=1, api_key="sk-test-FAKE",
                    base_url="", default_model="gpt-5-mini", extra_models="", timeout_seconds=0,
                    max_output_tokens=0, deployment="", api_version="")
        base.update(kw)
        return frappe._dict(base)

    def check(self, row):
        self.m._check_provider_row(row, bool(frappe.conf.get("pa_allow_private_llm_urls")))
        return row

    def test_defaults_and_clamps(self):
        r = self.check(self.row(label="  " + "x" * 80, timeout_seconds=0))
        self.assertEqual(r.timeout_seconds, 120)
        self.assertEqual(len(r.label), 60)
        self.assertEqual(self.check(self.row(timeout_seconds=3)).timeout_seconds, 10)
        self.assertEqual(self.check(self.row(timeout_seconds=9999)).timeout_seconds, 600)

    def test_max_output_tokens(self):
        self.check(self.row(max_output_tokens=256))
        for bad in (1, 255, 200001):
            with self.assertRaises(frappe.ValidationError):
                self.check(self.row(max_output_tokens=bad))

    def test_extra_models_dedupe_and_limits(self):
        r = self.check(self.row(extra_models=" a \n\nb\na\nc "))
        self.assertEqual(r.extra_models, "a\nb\nc")
        with self.assertRaises(frappe.ValidationError):
            self.check(self.row(extra_models="has space"))
        with self.assertRaises(frappe.ValidationError):
            self.check(self.row(extra_models="\n".join(f"m{i}" for i in range(101))))
        with self.assertRaises(frappe.ValidationError):
            self.check(self.row(default_model="x" * 121))

    def test_invalid_provider_and_required_key(self):
        with self.assertRaises(frappe.ValidationError):
            self.check(self.row(provider_id="gemini"))
        with self.assertRaises(frappe.ValidationError):
            self.check(self.row(api_key=""))
        self.check(self.row(api_key="", enabled=0))
        self.check(self.row(provider_id="openai_compatible", api_key="", base_url="https://example.com/v1"))
        with self.assertRaises(frappe.ValidationError):
            self.check(self.row(provider_id="openai_compatible", api_key="", base_url=""))

    def test_base_url_rules(self):
        for bad in ("http://example.com/v1", "https://user:pw@example.com/v1", "https://example.com/v1?x=1",
                    "https://127.0.0.1/v1", "https://10.0.0.5/v1"):
            with self.assertRaises(frappe.ValidationError, msg=bad):
                self.check(self.row(base_url=bad))
        r = self.check(self.row(base_url="https://api.example.com/v1/chat/completions"))
        self.assertEqual(r.base_url, "https://api.example.com/v1")

    def test_azure_rules(self):
        ok = dict(provider_id="azure_openai", base_url="https://res.openai.azure.com", deployment="gpt4o")
        r = self.check(self.row(**ok))
        self.assertEqual(r.api_version, "2024-10-21")
        with self.assertRaises(frappe.ValidationError):
            self.check(self.row(**{**ok, "deployment": ""}))
        with self.assertRaises(frappe.ValidationError):
            self.check(self.row(**{**ok, "base_url": ""}))
        with self.assertRaises(frappe.ValidationError):
            self.check(self.row(**{**ok, "base_url": "https://evil.example.com"}))

    def test_slug_assignment(self):
        taken = set()
        rows = [self.row(name="a", provider_id="openai_compatible", base_url="https://a.example.com/v1"),
                self.row(name="b", provider_id="openai_compatible", base_url="https://b.example.com/v1"),
                self.row(name="c", provider_id="openai", slug="openai")]
        stub = frappe._dict(llm_providers=rows, llm_backend_mode="AIDA only", flags=frappe._dict())
        stub.get = lambda k, d=None: stub[k] if k in stub else d
        with mock.patch.object(self.m, "_removed_provider_rows", return_value=[]):
            self.m.PACoreSettings._validate_llm_providers(stub)
        self.assertEqual([r.slug for r in rows], ["openai-compatible", "openai-compatible-2", "openai"])
        # a second validation keeps the slugs (immutable once set)
        with mock.patch.object(self.m, "_removed_provider_rows", return_value=[]):
            self.m.PACoreSettings._validate_llm_providers(stub)
        self.assertEqual([r.slug for r in rows], ["openai-compatible", "openai-compatible-2", "openai"])

    def test_saved_key_cannot_be_redirected(self):
        stored = {"r1": ("openai", "https://api.openai.com/v1", "", True)}
        moved = self.row(base_url="https://evil.example/v1", api_key="*****")
        with self.assertRaises(frappe.ValidationError):
            self.m._guard_stored_key(moved, stored)
        # a new key in the same save is allowed; an untouched endpoint is reported unchanged
        self.assertFalse(self.m._guard_stored_key(self.row(base_url="https://evil.example/v1"), stored))
        self.assertTrue(self.m._guard_stored_key(self.row(base_url="https://api.openai.com/v1", api_key="*****"), stored))
        with self.assertRaises(frappe.ValidationError):
            self.m._guard_stored_key(self.row(provider_id="anthropic"), stored)
        self.assertFalse(self.m._guard_stored_key(self.row(name="new1"), stored))

    def test_old_bad_endpoint_warns_instead_of_blocking(self):
        row = self.row(base_url="http://127.0.0.1:9/v1")
        with self.assertRaises(frappe.ValidationError):
            self.check(row)
        warned = []

        def msgprint(msg, *a, **kw):
            if kw.get("raise_exception"):
                raise frappe.ValidationError(msg)
            warned.append(msg)

        with mock.patch("frappe.msgprint", side_effect=msgprint):
            self.m._check_provider_row(row, False, unchanged=True)
        self.assertEqual(len(warned), 1)

    def test_row_limit(self):
        rows = [self.row(name=f"r{i}") for i in range(21)]
        stub = frappe._dict(llm_providers=rows, flags=frappe._dict())
        stub.get = lambda k, d=None: stub[k] if k in stub else d
        with mock.patch.object(self.m, "_removed_provider_rows", return_value=[]):
            with self.assertRaises(frappe.ValidationError):
                self.m.PACoreSettings._validate_llm_providers(stub)

    def test_unmigrated_site_is_a_noop(self):
        stub = frappe._dict(flags=frappe._dict())
        stub.get = lambda k, d=None: d
        with mock.patch("frappe.db.table_exists", return_value=False):
            self.m.PACoreSettings._validate_llm_providers(stub)
        self.assertEqual(stub.flags.removed_llm_rows, [])

    def test_removed_rows_and_auth_cleanup(self):
        with mock.patch("frappe.db.table_exists", return_value=True), \
                mock.patch("frappe.get_all", return_value=["a", "b", "c"]):
            self.assertEqual(self.m._removed_provider_rows([frappe._dict(name="b")]), ["a", "c"])
        with mock.patch("frappe.db.delete") as d:
            self.m._delete_removed_provider_keys(["a", "c"])
            d.assert_called_once_with(
                "__Auth", {"doctype": "PA LLM Provider", "fieldname": "api_key", "name": ("in", ["a", "c"])})
        with mock.patch("frappe.db.delete") as d:
            self.m._delete_removed_provider_keys([])
            d.assert_not_called()


class TestAdminEndpoints(unittest.TestCase):
    def setUp(self):
        from pibiassistant.pibiassistant_chat.api import llm_admin

        self.api = llm_admin
        self._user = frappe.session.user
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user(self._user)

    def test_requires_system_manager(self):
        frappe.set_user("Guest")
        for fn, args in ((self.api.test_provider, ("abc",)), (self.api.load_provider_models, ("abc",)),
                         (self.api.get_provider_catalog, ())):
            with self.assertRaises(frappe.PermissionError):
                fn(*args)

    def test_bad_row_names(self):
        for bad in ("", "a b", "../x", "x" * 141, None, 5):
            with self.assertRaises(frappe.ValidationError):
                self.api.test_provider(bad)

    def test_missing_row_gives_clear_error(self):
        with mock.patch("pibiassistant.pibiassistant_chat.api.llm_config.provider_by_name", return_value=None):
            with self.assertRaises(frappe.ValidationError) as cm:
                self.api.test_provider("abc123")
        self.assertIn("migrate", str(cm.exception))

    def test_catalog_survives_missing_package(self):
        res = self.api.get_provider_catalog()
        self.assertIsInstance(res["providers"], list)
        self.assertIn("allow_private", res)

    def test_result_never_contains_key(self):
        row = {"name": "abc", "slug": "openai", "label": "L", "provider_id": "openai"}

        class Fake:
            def __init__(self, row):
                pass

            def test(self):
                return {"ok": True, "detail": "https://x - 2 models", "error": "", "latency_ms": 5,
                        "models": [{"id": "m"}]}

        fake_mod = mock.MagicMock(get_provider=Fake, ProviderError=type("ProviderError", (Exception,), {}))
        with mock.patch("pibiassistant.pibiassistant_chat.api.llm_config.provider_by_name", return_value=row), \
                mock.patch.dict("sys.modules", {"pibiassistant.pibiassistant_chat.api.chat.providers": fake_mod}):
            res = self.api.test_provider("abc")
        self.assertTrue(res["ok"])
        self.assertEqual(res["label"], "L")
        self.assertNotIn("sk-", json.dumps(res))

    def test_unexpected_error_is_logged_without_details(self):
        row = {"name": "abc", "slug": "openai", "label": "L", "provider_id": "openai"}

        def boom(row):
            raise RuntimeError("secret sk-test-FAKE")

        fake_mod = mock.MagicMock(get_provider=boom, ProviderError=type("ProviderError", (Exception,), {}))
        with mock.patch("pibiassistant.pibiassistant_chat.api.llm_config.provider_by_name", return_value=row), \
                mock.patch.dict("sys.modules", {"pibiassistant.pibiassistant_chat.api.chat.providers": fake_mod}), \
                mock.patch("frappe.log_error") as log:
            res = self.api.test_provider("abc")
        self.assertFalse(res["ok"])
        self.assertNotIn("sk-test", json.dumps(res))
        self.assertNotIn("sk-test", json.dumps(log.call_args.kwargs))
        self.assertEqual(log.call_args.kwargs["title"], "LLM Provider Test Error")


class TestTranslationsAndStatic(unittest.TestCase):
    def test_es_rows_exist(self):
        import csv

        with open(os.path.join(BASE, "translations", "es.csv"), encoding="utf-8") as f:
            have = {r[0]: r[1] for r in csv.reader(f) if len(r) == 2}
        for key in ("Direct providers", "Chat backend", "AIDA only", "Test direct providers", "Use selected",
                    "{0} (direct)", "Save the settings first.", "Enter the API key"):
            self.assertTrue(have.get(key), key)

    def test_js_strings_are_translated(self):
        with open(os.path.join(DT, "pa_core_settings", "pa_core_settings.js"), encoding="utf-8") as f:
            js = f.read()
        import csv

        with open(os.path.join(BASE, "translations", "es.csv"), encoding="utf-8") as f:
            have = {r[0] for r in csv.reader(f) if len(r) == 2}
        for s in re.findall(r"__\('((?:[^'\\]|\\.)*)'\)", js):
            s = s.replace("\\'", "'")
            if "\\n" in s:
                continue
            self.assertIn(s, have, s)
