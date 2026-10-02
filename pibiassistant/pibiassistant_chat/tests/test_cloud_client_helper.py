"""Cloud-only endpoints refuse cleanly (ValidationError) when there is no cloud client."""

import unittest
from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.api import _helpers, connections, marketplace, packs, routing_preferences

CLIENT = "pibiassistant.pibiassistant_chat.pa_cloud_client.get_pa_cloud_client"


class TestCloudClientHelper(unittest.TestCase):
    def test_no_client_raises_validation_error(self):
        with patch(CLIENT, return_value=None):
            with self.assertRaises(frappe.ValidationError):
                _helpers.cloud_client_or_throw()

    def test_client_is_returned(self):
        with patch(CLIENT, return_value="client"):
            self.assertEqual(_helpers.cloud_client_or_throw(), "client")

    def test_modules_share_the_helper(self):
        self.assertIs(connections._client, _helpers.cloud_client_or_throw)
        self.assertIs(routing_preferences._client, _helpers.cloud_client_or_throw)
        self.assertIs(marketplace._get_client, _helpers.cloud_client_or_throw)
        self.assertIs(packs._client_or_throw, _helpers.cloud_client_or_throw)

    def test_helpers_never_return_an_unavailable_dict(self):
        with patch(CLIENT, return_value=None):
            for fn in (connections._client, routing_preferences._client, marketplace._get_client, packs._client_or_throw):
                with self.assertRaises(frappe.ValidationError):
                    fn()


if __name__ == "__main__":
    unittest.main()
