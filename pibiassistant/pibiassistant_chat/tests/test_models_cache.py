"""get_models caches a good upstream answer, never an error, and get_available_models reports failures."""

import unittest
from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.pibiassistant_chat.api import aida, models

CFG = ("https://aida.invalid", "key", "", "")


def _resp(status=200, payload=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload or {}
    r.text = text
    return r


class TestModelsCache(unittest.TestCase):
    def setUp(self):
        self._clear()
        for p in (patch.object(aida, "_get_aida_config", return_value=CFG), patch.object(aida, "_assert_can_use_aida")):
            p.start()
            self.addCleanup(p.stop)

    def _clear(self):
        for key in ("pa_aida_models:https://aida.invalid", "pa_aida_models_stale:https://aida.invalid"):
            frappe.cache().delete_value(key)

    def tearDown(self):
        self._clear()

    def test_second_call_is_served_from_cache(self):
        good = {"success": True, "providers": {"ollama": {"available": True, "models": ["m1"]}}}
        with patch.object(aida.requests, "get", return_value=_resp(200, good)) as get:
            self.assertEqual(aida.get_models(), good)
            self.assertEqual(aida.get_models(), good)
            self.assertEqual(get.call_count, 1)
            aida.get_models(refresh=1)
            self.assertEqual(get.call_count, 2)

    def test_errors_are_not_cached(self):
        with patch.object(aida.requests, "get", return_value=_resp(500, text="boom")) as get:
            self.assertFalse(aida.get_models()["success"])
            self.assertFalse(aida.get_models()["success"])
            self.assertEqual(get.call_count, 2)

    def test_errors_never_leak_upstream_text(self):
        with patch.object(aida.requests, "get", return_value=_resp(500, text="SECRET-UPSTREAM-BODY")), patch.object(
            frappe, "log_error"
        ) as log:
            self.assertNotIn("SECRET", str(aida.get_models()))
            self.assertIn("SECRET-UPSTREAM-BODY", log.call_args.kwargs["message"])
        with patch.object(aida.requests, "get", side_effect=RuntimeError("10.0.0.5 refused")), patch.object(
            frappe, "log_error"
        ):
            self.assertNotIn("10.0.0.5", str(aida.get_models()))

    def test_stale_list_is_served_while_a_refresh_is_enqueued(self):
        stale = {"success": True, "providers": {"ollama": {"available": True, "models": ["old"]}}}
        frappe.cache().set_value("pa_aida_models_stale:https://aida.invalid", stale, expires_in_sec=60)
        with patch.object(aida.requests, "get") as get, patch.object(frappe, "enqueue") as enqueue:
            self.assertEqual(aida.get_models(), stale)
            get.assert_not_called()
            self.assertEqual(
                enqueue.call_args.args[0], "pibiassistant.pibiassistant_chat.api.aida.refresh_models_cache"
            )

    def test_refresh_forces_a_synchronous_fetch_and_updates_both_entries(self):
        stale = {"success": True, "providers": {"ollama": {"available": True, "models": ["old"]}}}
        new = {"success": True, "providers": {"ollama": {"available": True, "models": ["new"]}}}
        frappe.cache().set_value("pa_aida_models_stale:https://aida.invalid", stale, expires_in_sec=60)
        with patch.object(aida.requests, "get", return_value=_resp(200, new)):
            self.assertEqual(aida.get_models(refresh=1), new)
        self.assertEqual(frappe.cache().get_value("pa_aida_models:https://aida.invalid", expires=True), new)
        self.assertEqual(frappe.cache().get_value("pa_aida_models_stale:https://aida.invalid", expires=True), new)

    def test_upstream_failure_yields_error_not_empty_success(self):
        with patch.object(aida.requests, "get", side_effect=RuntimeError("down")):
            result = models._aida_models()
        self.assertFalse(result["success"])
        self.assertTrue(result["error"])
        self.assertEqual(result["models"], [])


if __name__ == "__main__":
    unittest.main()
