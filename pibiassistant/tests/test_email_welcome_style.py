"""The welcome email must follow the UI guidelines and be translatable."""

import frappe
from frappe.utils.jinja import get_email_from_template

from pibiassistant.tests.base_test import BaseAssistantTest


class TestEmailWelcomeStyle(BaseAssistantTest):
    def _render(self, lang):
        prev = frappe.local.lang
        frappe.local.lang = lang
        try:
            return get_email_from_template("pa_welcome", {"heading": "H", "cta_url": "https://x/aida/"})[0]
        finally:
            frappe.local.lang = prev

    def test_no_accent_borders_or_system_fonts(self):
        html = self._render("en")
        self.assertNotIn("border-left", html)
        self.assertNotIn("border-top", html)
        self.assertNotIn("system-ui", html)
        self.assertNotIn("Segoe", html)
        self.assertIn("Open your workspace", html)

    def test_every_text_goes_through_translation(self):
        jenv = frappe.get_jenv()
        original = jenv.globals["_"]
        jenv.globals["_"] = lambda text, *a, **k: "[T]" + original(text)
        try:
            html = get_email_from_template("pa_welcome", {"heading": "H", "cta_url": "https://x/aida/"})[0]
        finally:
            jenv.globals["_"] = original
        self.assertEqual(html.count("[T]"), 9)
        self.assertIn("[T]Open your workspace", html)
