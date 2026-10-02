from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.api import oauth_discovery
from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.utils import oauth_compat


class TestOAuthDiscoveryShared(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        for target in ("frappe.oauth.get_server_url", "frappe.integrations.oauth2.get_server_url", "pibiassistant.api.oauth_discovery.get_server_url"):
            patcher = patch(target, return_value="https://zz.example.test")
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_openid_configuration_advertises_code_flow_only(self):
        frappe.local.response = frappe._dict()
        oauth_discovery.openid_configuration()
        meta = frappe.local.response
        self.assertEqual(meta["response_types_supported"], ["code"])
        self.assertNotIn("id_token_signing_alg_values_supported", meta)

    def test_documentation_urls_agree_across_documents(self):
        auth = oauth_discovery.authorization_server_metadata()
        resource = oauth_discovery.protected_resource_metadata()
        self.assertEqual(auth["service_documentation"], resource["resource_documentation"])

    def test_issuer_agrees_between_documents(self):
        frappe.local.response = frappe._dict()
        oauth_discovery.openid_configuration()
        self.assertEqual(
            frappe.local.response["issuer"], oauth_discovery.authorization_server_metadata()["issuer"]
        )

    def test_parse_scopes_dedupes_and_splits(self):
        self.assertEqual(oauth_compat.parse_scopes("openid profile\nall\nopenid"), ["openid", "profile", "all"])
        self.assertEqual(oauth_compat.parse_scopes(None), [])

    def test_del_none_values(self):
        data = {"a": 1, "b": None}
        oauth_compat.del_none_values(data)
        self.assertEqual(data, {"a": 1})

    def test_registration_response_shape(self):
        doc = MagicMock(client_id="cid", app_name="App")
        doc.get_password.return_value = "sec"
        meta = SimpleNamespace(
            token_endpoint_auth_method=None,
            client_uri="https://x.test",
            logo_uri=None,
            tos_uri=None,
            policy_uri=None,
            scope="all",
            contacts=None,
            software_id=None,
            software_version="1",
        )
        out = oauth_compat._registration_response(doc, ["https://x.test/cb"], meta)
        self.assertEqual(out["client_id"], "cid")
        self.assertEqual(out["client_secret"], "sec")
        self.assertEqual(out["token_endpoint_auth_method"], "client_secret_basic")
        self.assertEqual(out["client_uri"], "https://x.test")
        self.assertEqual(out["scope"], "all")
        self.assertEqual(out["software_version"], "1")
        self.assertNotIn("logo_uri", out)
        self.assertNotIn("contacts", out)
