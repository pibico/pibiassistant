"""An export for a session with no messages and no state is refused instead of leaving an empty File."""

import frappe

from pibiassistant.pibiassistant_chat.api.chat.debug_bundle import export_debug_bundle
from pibiassistant.tests.base_test import BaseAssistantTest


class TestDebugBundleEmpty(BaseAssistantTest):
    def test_empty_session_is_refused_and_no_file_is_created(self):
        before = frappe.db.count("File", {"file_name": ["like", "debug-bundle-ZZ-empty%"]})
        with self.assertRaises(frappe.DoesNotExistError):
            export_debug_bundle("ZZ-empty-session")
        self.assertEqual(frappe.db.count("File", {"file_name": ["like", "debug-bundle-ZZ-empty%"]}), before)
