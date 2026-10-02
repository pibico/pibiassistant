from unittest.mock import patch

import frappe

from pibiassistant.mcp.server import MCPServer
from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.tests.mcp_test_utils import rpc


class TestResourcesReadParams(BaseAssistantTest):
    def setUp(self):
        self.server = MCPServer("test")

    def _code(self, params):
        status, body = rpc(self.server, {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": params}, {})
        self.assertEqual(status, 400, body)
        return body["error"]["code"]

    def test_non_string_uri_is_invalid_params(self):
        for params in ({"uri": None}, {"uri": 5}, {}, {"uri": ["pa://skills/x"]}):
            self.assertEqual(self._code(params), -32602, params)

    def test_permission_denied_is_invalid_params_not_internal(self):
        with patch(
            "pibiassistant.api.handlers.resources.SkillManager.read_skill_content",
            side_effect=frappe.PermissionError("no"),
        ):
            self.assertEqual(self._code({"uri": "pa://skills/some-private-skill"}), -32602)

    def test_prompt_permission_denied_is_invalid_params(self):
        denied = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "denied"}}
        with patch("pibiassistant.api.handlers.prompts.handle_prompts_get", return_value=denied):
            status, body = rpc(
                self.server, {"jsonrpc": "2.0", "id": 1, "method": "prompts/get", "params": {"name": "x"}}, {}
            )
        self.assertEqual(body["error"]["code"], -32602)
