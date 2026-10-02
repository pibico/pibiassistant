from datetime import timedelta
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import now_datetime
from werkzeug.wrappers import Response

from pibiassistant.api import pa_endpoint
from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.utils.auth import check_assistant_enabled, validate_api_credentials

EMAIL = "zz-auth-helpers@example.com"
IP = "zz-test-ip"


class TestApiAuthHelpers(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        user = frappe.new_doc("User")
        user.update({"email": EMAIL, "first_name": "ZZ Auth", "send_welcome_email": 0, "enabled": 1})
        # Password fields read back masked after insert, so keep the plaintext.
        cls.api_key = "zzkey" + frappe.generate_hash(length=10)
        cls.api_secret = "zzsecret" + frappe.generate_hash(length=10)
        user.api_key, user.api_secret = cls.api_key, cls.api_secret
        user.flags.ignore_permissions = True
        user.insert()

    def setUp(self):
        frappe.db.set_value("User", EMAIL, {"enabled": 1, "assistant_enabled": 1})
        frappe.local.request_ip = IP
        frappe.cache.delete(pa_endpoint._auth_fail_key())
        self.addCleanup(frappe.cache.delete, pa_endpoint._auth_fail_key())

    def _request(self, header):
        request = MagicMock()
        request.headers = {"Authorization": header}
        request.url = "https://internal.local/api/method/pibiassistant.api.pa_endpoint.handle_mcp"
        original = getattr(frappe.local, "request", None)
        frappe.local.request = request
        self.addCleanup(setattr, frappe.local, "request", original)

    def test_valid_credentials_resolve_user(self):
        self.assertEqual(validate_api_credentials(self.api_key, self.api_secret), EMAIL)

    def test_wrong_or_empty_credentials_fail(self):
        self.assertIsNone(validate_api_credentials(self.api_key, "wrong"))
        self.assertIsNone(validate_api_credentials(self.api_key, ""))
        self.assertIsNone(validate_api_credentials("", self.api_secret))
        self.assertIsNone(validate_api_credentials("nokey", self.api_secret))

    def test_disabled_user_fails(self):
        frappe.db.set_value("User", EMAIL, "enabled", 0)
        self.assertIsNone(validate_api_credentials(self.api_key, self.api_secret))

    def test_assistant_enabled_flag(self):
        frappe.db.set_value("User", EMAIL, "assistant_enabled", 0)
        self.assertFalse(check_assistant_enabled(EMAIL))
        frappe.db.set_value("User", EMAIL, "assistant_enabled", 1)
        self.assertTrue(check_assistant_enabled(EMAIL))

    def test_bad_token_gets_401_without_exception_text(self):
        self._request("token nokey:nosecret")
        result = pa_endpoint._authenticate_mcp_request()
        self.assertIsInstance(result, Response)
        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.headers["WWW-Authenticate"].count("resource_metadata="), 1)

    def test_lockout_returns_429_after_repeated_failures(self):
        self._request("token nokey:nosecret")
        for _i in range(pa_endpoint._AUTH_FAIL_LIMIT):
            self.assertEqual(pa_endpoint._authenticate_mcp_request().status_code, 401)
        self.assertEqual(pa_endpoint._authenticate_mcp_request().status_code, 429)

    def test_bearer_for_disabled_user_is_rejected(self):
        frappe.db.set_value("User", EMAIL, "enabled", 0)
        token = MagicMock(status="Active", user=EMAIL, expiration_time=now_datetime() + timedelta(hours=1))
        self._request("Bearer abc")
        with patch.object(pa_endpoint.frappe, "get_doc", return_value=token):
            result = pa_endpoint._authenticate_mcp_request()
        self.assertIsInstance(result, Response)
        self.assertEqual(result.status_code, 401)
        self.assertIn("User is disabled", result.headers["WWW-Authenticate"])
