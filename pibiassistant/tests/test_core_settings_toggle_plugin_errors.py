import frappe
from frappe.tests.utils import FrappeTestCase

from pibiassistant.pibiassistant_core.doctype.prompt_template import prompt_template as pt


class TestTogglePluginErrors(FrappeTestCase):
    def _settings(self):
        return frappe.get_single("PA Core Settings")

    def test_invalid_action_is_plain_validation_error(self):
        before = frappe.db.count("Error Log")
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._settings().toggle_plugin("core", "bogus")
        self.assertIn("bogus", str(ctx.exception))
        self.assertNotIn("No se ha podido", str(ctx.exception))
        self.assertEqual(frappe.db.count("Error Log"), before)

    def test_unknown_plugin_does_not_write_error_log(self):
        before = frappe.db.count("Error Log")
        with self.assertRaises(frappe.ValidationError):
            self._settings().toggle_plugin("zz_no_such_plugin", "enable")
        self.assertEqual(frappe.db.count("Error Log"), before)

    def test_prompt_clamp_limit_handles_infinity(self):
        self.assertEqual(pt.clamp_limit(float("inf"), 20, 100), 20)
        self.assertEqual(pt.clamp_limit(0, 20, 100), 20)
        self.assertEqual(pt.clamp_limit("x", 20, 100), 20)
        self.assertEqual(pt.clamp_limit(500, 20, 100), 100)
