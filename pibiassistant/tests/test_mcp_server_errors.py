from pibiassistant.core.base_tool import BaseTool
from pibiassistant.mcp.server import MCPServer
from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.tests.mcp_test_utils import registry_with, rpc


class _Tool(BaseTool):
    def __init__(self, name, outcome):
        super().__init__()
        self.name = name
        self.description = "fixture"
        self.inputSchema = {"type": "object", "properties": {"doc": {"type": "string"}}}
        self.requires_permission = None
        self._outcome = outcome

    def execute(self, arguments):
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome

    def log_execution(self, *args, **kwargs):
        return None


def _call(server, registry, name, arguments):
    return rpc(
        server,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
        registry,
    )


class TestToolCallErrors(BaseAssistantTest):
    def setUp(self):
        self.server = MCPServer("test")

    def test_exception_message_has_no_traceback_or_paths(self):
        reg = registry_with(_Tool("boom", RuntimeError("kaboom")))
        _, body = _call(self.server, reg, "boom", {})
        result = body["result"]
        text = result["content"][0]["text"]
        self.assertTrue(result["isError"])
        self.assertIn("kaboom", text)
        self.assertNotIn("Traceback", text)
        self.assertNotIn("/home/", text)

    def test_tool_reported_failure_sets_is_error(self):
        reg = registry_with(_Tool("soft_fail", {"success": False, "error": "nope"}))
        _, body = _call(self.server, reg, "soft_fail", {})
        self.assertTrue(body["result"]["isError"])

    def test_success_is_not_error(self):
        reg = registry_with(_Tool("fine", {"ok": 1}))
        _, body = _call(self.server, reg, "fine", {})
        self.assertFalse(body["result"]["isError"])

    def test_non_dict_arguments_are_invalid_params(self):
        reg = registry_with(_Tool("fine", {"ok": 1}))
        status, body = _call(self.server, reg, "fine", "notadict")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], -32602)
        self.assertNotIn("Traceback", str(body))
