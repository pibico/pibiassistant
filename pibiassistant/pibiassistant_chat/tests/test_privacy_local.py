# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""GDPR endpoints that survive PA Cloud: export and restriction work on site-local data."""

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest


class TestPrivacyLocal(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def test_export_my_data_is_local_and_carries_pao_block(self):
        from pibiassistant.pibiassistant_chat.api import privacy

        result = privacy.export_my_data()
        self.assertEqual(result["status"], "success")
        pao = result["data"]["pao"]
        self.assertIn("pao_messages_count", pao)
        self.assertIn("pao_messages", pao)

    def test_restrict_my_processing_flips_the_local_flag(self):
        from pibiassistant.pibiassistant_chat.api import privacy

        result = privacy.restrict_my_processing(restrict="true")
        self.assertEqual(result, {"status": "success", "processing_restricted": True})
        flag = frappe.db.get_value("PA Chat User Preferences", "Administrator", "processing_restricted")
        self.assertEqual(flag, 1)
        privacy.restrict_my_processing(restrict=False)
        self.assertEqual(
            frappe.db.get_value("PA Chat User Preferences", "Administrator", "processing_restricted"), 0
        )

    def test_erase_requires_a_password(self):
        from pibiassistant.pibiassistant_chat.api import privacy

        with self.assertRaises(frappe.ValidationError):
            privacy.erase_my_data()
