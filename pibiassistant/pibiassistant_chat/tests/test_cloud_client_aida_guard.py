"""get_pa_cloud_client never builds a client: PA Cloud was retired."""

from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client
from pibiassistant.tests.base_test import BaseAssistantTest

PWD = "frappe.utils.password.get_decrypted_password"


class TestCloudClientAidaGuard(BaseAssistantTest):
    def test_aida_key_returns_none_even_when_registered(self):
        frappe.db.set_single_value("PA Chat Settings", "registration_status", "Registered")
        frappe.db.set_single_value("PA Chat Settings", "tenant_id", "stale-tenant")
        with patch(PWD, return_value="some-key"):
            self.assertIsNone(get_pa_cloud_client())

    def test_without_key_there_is_still_no_client(self):
        frappe.db.set_single_value("PA Chat Settings", "registration_status", "Registered")
        with patch(PWD, return_value=None):
            self.assertIsNone(get_pa_cloud_client())
