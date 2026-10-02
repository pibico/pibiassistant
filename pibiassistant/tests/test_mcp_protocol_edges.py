from pibiassistant.mcp.server import MCPServer
from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.tests.mcp_test_utils import rpc


class TestProtocolEdges(BaseAssistantTest):
    def setUp(self):
        self.server = MCPServer("test")

    def _error_code(self, payload):
        status, body = rpc(self.server, payload, {})
        self.assertEqual(status, 400, body)
        self.assertNotIn("Traceback", str(body))
        return body["error"]["code"]

    def test_non_object_params_are_invalid_params(self):
        self.assertEqual(self._error_code({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": "bad"}), -32602)

    def test_batch_and_null_bodies_are_invalid_request(self):
        self.assertEqual(self._error_code([{"jsonrpc": "2.0", "id": 1, "method": "ping"}]), -32600)
        self.assertEqual(self._error_code(None), -32600)

    def test_null_params_are_treated_as_empty(self):
        status, body = rpc(self.server, {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": None}, {})
        self.assertEqual(status, 200)
        self.assertEqual(body["result"], {})

    def test_unknown_skill_resource_is_invalid_params(self):
        code = self._error_code(
            {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "pa://skills/zz-nope"}}
        )
        self.assertEqual(code, -32602)

    def test_initialize_negotiates_protocol_version(self):
        _, body = rpc(
            self.server,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
            {},
        )
        self.assertEqual(body["result"]["protocolVersion"], "2024-11-05")
        _, body = rpc(
            self.server,
            {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}},
            {},
        )
        self.assertIn(body["result"]["protocolVersion"], ("2025-06-18", "2025-03-26", "2024-11-05"))
        self.assertNotEqual(body["result"]["protocolVersion"], "1999-01-01")

    def test_prompts_get_null_arguments_and_bogus_doctype(self):
        _, body = rpc(
            self.server,
            {"jsonrpc": "2.0", "id": 1, "method": "prompts/get", "params": {"name": "sales_analysis", "arguments": None}},
            {},
        )
        # null arguments behave like {}: a clean "missing argument" error, not a crash
        self.assertEqual(body["error"]["code"], -32602)
        self.assertIn("analysis_focus", body["error"]["message"])
        status, body = rpc(
            self.server,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "prompts/get",
                "params": {"name": "data_quality_audit", "arguments": {"doctype_name": "ZZ No Such DocType"}},
            },
            {},
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], -32602)

    def test_notification_without_id_is_accepted(self):
        self.assertTrue(self.server._is_notification({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_notification_method_with_id_is_a_request(self):
        status, body = rpc(
            self.server, {"jsonrpc": "2.0", "id": 7, "method": "notifications/initialized"}, {}
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], -32601)

    def test_unknown_tool_message_does_not_list_every_tool(self):
        registry = {f"zz_tool_{i}": {"name": f"zz_tool_{i}", "fn": lambda **k: {}} for i in range(30)}
        _, body = rpc(
            self.server,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "zz_nope", "arguments": {}}},
            registry,
        )
        text = body["result"]["content"][0]["text"]
        self.assertIn("zz_nope", text)
        self.assertNotIn("zz_tool_1", text)
        self.assertLess(len(text), 200)
