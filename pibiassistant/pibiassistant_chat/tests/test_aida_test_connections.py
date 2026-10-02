"""test_connections checks the three APIs in parallel and caches the answer."""

import time
import unittest
from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.pibiassistant_chat.api import aida


def _slow_get(*_a, **_k):
    time.sleep(0.5)
    r = MagicMock()
    r.status_code = 200
    r.text = ""
    return r


class TestConnections(unittest.TestCase):
    def setUp(self):
        self._orig_user = frappe.session.user
        frappe.set_user("Administrator")
        self.addCleanup(frappe.set_user, self._orig_user)
        frappe.cache().delete_value("pa_aida_health:Chat:True|Conv:True|Voice:False")
        for p in (
            patch.object(aida, "_get_aida_config", return_value=("Chat", "k", "", "")),
            patch.object(aida, "_get_convert_config", return_value=("Conv", "k")),
            patch.object(aida, "_get_voice_config", return_value=("Voice", "")),
        ):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        frappe.cache().delete_value("pa_aida_health:Chat:True|Conv:True|Voice:False")

    def test_parallel_cached_and_keys_kept(self):
        with patch.object(aida.requests, "get", side_effect=_slow_get) as get:
            started = time.monotonic()
            result = aida.test_connections()
            self.assertLess(time.monotonic() - started, 0.9)
            self.assertEqual(get.call_count, 2)
            self.assertTrue(result["Chat API"]["ok"])
            self.assertEqual(result["Chat API"]["detail"], "Chat — HTTP 200")
            self.assertFalse(result["Voice API"]["ok"])
            self.assertEqual(result["Voice API"]["error"], frappe._("Not configured"))
            self.assertEqual(aida.test_connections(), result)
            self.assertEqual(get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
