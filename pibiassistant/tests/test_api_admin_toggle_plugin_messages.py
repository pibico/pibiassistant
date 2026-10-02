import frappe

from pibiassistant.api.admin.plugins import toggle_plugin
from pibiassistant.tests.base_test import BaseAssistantTest


class TestToggleMessages(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def test_unknown_plugin_is_a_user_error_not_an_error_log(self):
        before = frappe.db.count("Error Log")
        result = toggle_plugin("ZZ-nonexistent", True)
        self.assertFalse(result["success"])
        self.assertIn("ZZ-nonexistent", result["message"])
        self.assertEqual(frappe.db.count("Error Log"), before)

    def test_message_goes_through_translation_template(self):
        import inspect

        src = inspect.getsource(toggle_plugin)
        self.assertIn('_("Plugin \'{0}\' enabled successfully")', src)
        self.assertIn('_("Plugin \'{0}\' disabled successfully")', src)
