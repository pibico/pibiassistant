"""The cancel registry must survive multi-worker gunicorn: storage is
frappe.cache (Redis), not process memory."""

import unittest
from unittest.mock import MagicMock, patch

from pibiassistant.pibiassistant_chat.api.chat import cancel as cancel_mod


class TestCancelRegistryRedis(unittest.TestCase):
    def test_mark_uses_cache_with_ttl(self):
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cancel_mod.mark_cancelled("s1")
            cache.set_value.assert_called_once_with("pa_cancel:s1", "1", expires_in_sec=120)

    def test_is_cancelled_reads_cache(self):
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cache.get_value.return_value = "1"
            self.assertTrue(cancel_mod.is_cancelled("s1"))
            cache.get_value.return_value = None
            self.assertFalse(cancel_mod.is_cancelled("s1"))

    def test_is_cancelled_reads_with_expires_true(self):
        # frappe.cache().get_value() defaults to use_local_cache=True, which
        # memoizes a None miss into frappe.local.cache and would keep serving
        # stale "not cancelled" to a long-lived worker after a first miss.
        # expires=True on the read is the only thing that prevents that.
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cache.get_value.return_value = "1"
            cancel_mod.is_cancelled("s1")
            cache.get_value.assert_called_with("pa_cancel:s1", expires=True)

    def test_clear_deletes_key(self):
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cancel_mod.clear("s1")
            cache.delete_value.assert_called_once_with("pa_cancel:s1")

    def test_empty_session_id_is_noop(self):
        with patch.object(cancel_mod, "frappe") as fm:
            self.assertFalse(cancel_mod.is_cancelled(""))
            cancel_mod.mark_cancelled("")
            cancel_mod.clear("")
            fm.cache.assert_not_called()
