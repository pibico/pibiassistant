import ast
import os
import re
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(BASE, *parts), encoding="utf-8") as f:
        return f.read()


class TestAdminCoreSettingsStatic(unittest.TestCase):
    def test_buttons_force_refresh(self):
        js = _read("pibiassistant_core", "doctype", "pa_core_settings", "pa_core_settings.js")
        self.assertIn("args: { refresh: show_message ? 1 : 0 }", js)
        self.assertIn("args: { refresh: 1 }", js)

    def test_result_icons_single_class_attribute(self):
        js = _read("pibiassistant_core", "doctype", "pa_core_settings", "pa_core_settings.js")
        for tag in re.findall(r"<i [^>]*>", js):
            self.assertEqual(tag.count("class="), 1, tag)

    def test_admin_api_forwards_silent(self):
        js = _read("public", "js", "pa_admin", "api.js")
        self.assertIn("silent: true,", js)

    def test_log_error_has_title_and_message(self):
        for rel in (("pibiassistant_core", "server.py"),
                    ("pibiassistant_core", "doctype", "pa_core_settings", "pa_core_settings.py")):
            tree = ast.parse(_read(*rel))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "log_error":
                    self.assertTrue(any(k.arg == "title" for k in node.keywords), rel)

    def test_reduced_motion_global_rule(self):
        css = _read("public", "css", "pa_admin.css")
        self.assertIn(".pa-admin-container *::after { transition-duration: 0.01ms", css)

    def test_vendor_dead_files_gone(self):
        self.assertFalse(os.path.exists(os.path.join(BASE, "public", "vendor", "pibico", "pibico.css")))
        self.assertNotIn("--pibico-grad-banner", _read("public", "vendor", "pibico", "tokens.css"))

    def test_llm_form_js_rules(self):
        js = _read("pibiassistant_core", "doctype", "pa_core_settings", "pa_core_settings.js")
        self.assertIn('frappe.ui.form.on("PA LLM Provider"', js)
        self.assertIn("pibiassistant_panel()", js)
        self.assertNotIn("frappe.msgprint(r.message", js)

    def test_llm_css_has_no_accent_borders(self):
        css = _read("public", "css", "pa_core_settings.css")
        for line in css.splitlines():
            if ".pa-ps-llm" in line:
                self.assertNotRegex(line, r"border-(left|top)\s*:")
                self.assertNotIn("font-family: serif", line)

