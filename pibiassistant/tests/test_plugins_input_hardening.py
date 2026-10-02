# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""attach_file base64 tolerance, browser tool clamps, citation URLs, stale visualization copy."""

import base64
import importlib
import unittest

import frappe

from pibiassistant.plugins.core.tools.attach_file import normalize_base64
from pibiassistant.plugins.pao.tools.browser_take_screenshot import BrowserTakeScreenshot
from pibiassistant.plugins.pao.tools.browser_wait_for_page import MAX_WAIT_MS, BrowserWaitForPage
from pibiassistant.utils import attachments


class TestBase64Normalising(unittest.TestCase):
    PAYLOAD = bytes(range(256)) * 3

    def _decode(self, text):
        return attachments.decode_base64(normalize_base64(text))

    def test_wrapped_unpadded_and_urlsafe(self):
        standard = base64.b64encode(self.PAYLOAD).decode()
        wrapped = "\n".join(standard[i : i + 76] for i in range(0, len(standard), 76))
        urlsafe = base64.urlsafe_b64encode(self.PAYLOAD).decode().rstrip("=")
        for variant in (standard, wrapped, urlsafe, "data:application/pdf;base64," + wrapped):
            self.assertEqual(self._decode(variant), self.PAYLOAD)

    def test_garbage_still_rejected(self):
        with self.assertRaises(attachments.AttachmentError):
            self._decode("not base64 !!!")


class TestBrowserClamps(unittest.TestCase):
    def test_wait_timeout_is_clamped(self):
        tool = BrowserWaitForPage()
        for raw, expected in ((-5, 1000), (99999999, MAX_WAIT_MS), (None, 10000), (5000, 5000)):
            self.assertEqual(tool.get_tool_params({"timeout_ms": raw})["timeout_ms"], expected)

    def test_screenshot_quality_is_clamped(self):
        tool = BrowserTakeScreenshot()
        for raw, expected in ((0, 1), (500, 100), (None, 80), (55, 55)):
            self.assertEqual(tool.get_tool_params({"quality": raw})["quality"], expected)

    def test_no_shared_timeout_setter(self):
        from pibiassistant.plugins.pao.tools.base_browser_tool import BaseBrowserTool

        self.assertFalse(hasattr(BaseBrowserTool, "set_timeout"))


class TestCitationUrl(unittest.TestCase):
    def test_form_url_quotes_names(self):
        url = frappe.utils.get_url_to_form("Sales Invoice", "ACC-SINV-2025-00004")
        self.assertTrue(url.endswith("/app/sales-invoice/ACC-SINV-2025-00004"), url)


class TestVisualizationLegacyRemoved(unittest.TestCase):
    def test_stale_modules_are_gone_and_plugin_imports(self):
        for name in ("plugin_registry", "utils.chart_suggestions", "utils.dashboard_helpers", "constants"):
            with self.assertRaises(ImportError):
                importlib.import_module(f"pibiassistant.plugins.visualization.{name}")
        plugin = importlib.import_module("pibiassistant.plugins.visualization.plugin")
        self.assertTrue(plugin)
