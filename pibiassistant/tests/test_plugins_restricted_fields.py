"""Golden values for the restricted-field set shared by the document tools."""

from pibiassistant.plugins.core.field_guard import restricted_fields_for_doctype
from pibiassistant.tests.base_test import BaseAssistantTest


class TestRestrictedFields(BaseAssistantTest):
    def test_sensitive_for_everyone(self):
        for role in ("System Manager", "PA User"):
            fields = restricted_fields_for_doctype("ToDo", role)
            self.assertLessEqual({"password", "api_secret", "iban"}, fields)

    def test_admin_only_for_pa_user_only(self):
        pa = restricted_fields_for_doctype("User", "PA User")
        sm = restricted_fields_for_doctype("User", "System Manager")
        self.assertLessEqual({"owner", "docstatus", "roles", "enabled"}, pa)
        self.assertTrue({"owner", "docstatus", "roles", "enabled"}.isdisjoint(sm))
        self.assertIn("last_login", sm)

    def test_star_doctype_adds_no_names(self):
        self.assertEqual(
            restricted_fields_for_doctype("System Settings", "PA User"),
            restricted_fields_for_doctype("ToDo", "PA User") | {"password_reset_limit", "session_expiry",
                "session_expiry_mobile", "email_footer_address", "backup_path", "backup_path_db",
                "backup_path_files", "backup_path_private_files", "encryption_key"},
        )
