import json
import math
from unittest.mock import patch

import frappe

from pibiassistant.core.base_tool import BaseTool, redact_sensitive
from pibiassistant.core.tool_registry import get_tool_registry
from pibiassistant.mcp.server import MCPServer
from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.tests.mcp_test_utils import registry_with, rpc
from pibiassistant.utils.json_safe import dumps_strict, finite


class _Tool(BaseTool):
    def __init__(self, name="zz_hardening_tool", result=None, boom=False):
        super().__init__()
        self.name = name
        self.description = "fixture"
        self.inputSchema = {"type": "object", "properties": {}, "additionalProperties": True}
        self._result = result
        self._boom = boom

    def execute(self, arguments):
        if self._boom:
            raise RuntimeError("kaboom")
        return self._result


class TestStrictJson(BaseAssistantTest):
    def test_finite_replaces_non_finite_at_any_depth(self):
        data = {"a": float("nan"), "b": [1.5, float("inf"), {"c": -math.inf}], "d": (float("nan"),)}
        self.assertEqual(finite(data), {"a": None, "b": [1.5, None, {"c": None}], "d": [None]})

    def test_dumps_strict_is_strict_json(self):
        text = dumps_strict({"x": float("nan"), "y": float("inf")}, indent=2)
        self.assertEqual(json.loads(text, parse_constant=self._reject), {"x": None, "y": None})

    @staticmethod
    def _reject(token):
        raise AssertionError(f"invalid JSON token {token}")

    def test_mcp_tools_call_emits_strict_json(self):
        tool = _Tool(result={"mean": float("nan"), "rows": [1, float("inf")]})
        status, body = rpc(
            MCPServer("test"),
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool.name, "arguments": {}}},
            registry_with(tool),
        )
        self.assertEqual(status, 200, body)
        text = body["result"]["content"][0]["text"]
        payload = json.loads(text, parse_constant=self._reject)
        self.assertIsNone(payload["result"]["mean"])
        self.assertEqual(payload["result"]["rows"], [1, None])


class TestSecretRedaction(BaseAssistantTest):
    def test_redaction_at_every_depth(self):
        args = {"data": {"new_password": "s3cret", "nested": [{"api_secret": "x"}], "name": "ok"}, "token": "t"}
        out = redact_sensitive(args)
        self.assertEqual(out["token"], "***REDACTED***")
        self.assertEqual(out["data"]["new_password"], "***REDACTED***")
        self.assertEqual(out["data"]["nested"][0]["api_secret"], "***REDACTED***")
        self.assertEqual(out["data"]["name"], "ok")
        self.assertEqual(args["data"]["new_password"], "s3cret")

    def test_generic_exception_error_log_has_no_secret(self):
        tool = _Tool(boom=True)
        logged = []
        with patch("frappe.log_error", side_effect=lambda **kw: logged.append(kw)):
            result = tool._safe_execute({"data": {"new_password": "s3cret-value", "api_secret": "zz-sec"}})
        self.assertFalse(result["success"])
        text = json.dumps(logged, default=str)
        self.assertIn("kaboom", text)
        self.assertNotIn("s3cret-value", text)
        self.assertNotIn("zz-sec", text)

    def test_audit_row_has_no_secret(self):
        tool = _Tool(boom=True)
        tool._safe_execute({"data": {"new_password": "s3cret-value"}})
        row = frappe.get_all(
            "PA Audit Log", filters={"tool_name": tool.name}, fields=["input_data"], order_by="creation desc", limit=1
        )
        self.assertTrue(row)
        self.assertNotIn("s3cret-value", row[0].input_data or "")


class TestPermissionForGivenUser(BaseAssistantTest):
    def test_registry_checks_the_passed_user_not_the_session_user(self):
        tool = _Tool()
        tool.requires_permission = "ToDo"
        registry = get_tool_registry()
        frappe.set_user("Administrator")
        self.assertTrue(registry._check_tool_permission(tool, "Administrator"))
        self.assertFalse(registry._check_tool_permission(tool, "Guest"))


class TestPromptGetNameValidation(BaseAssistantTest):
    def test_non_string_prompt_name_is_invalid_params_without_error_log(self):
        before = frappe.db.count("Error Log")
        for name in (["x"], 5, {}, ""):
            status, body = rpc(
                MCPServer("test"),
                {"jsonrpc": "2.0", "id": 1, "method": "prompts/get", "params": {"name": name}},
                {},
            )
            self.assertEqual(body["error"]["code"], -32602, name)
        self.assertEqual(frappe.db.count("Error Log"), before)


class TestAdminErrorLogTitles(BaseAssistantTest):
    def test_long_error_does_not_turn_into_a_500(self):
        from pibiassistant.api.admin import prompts

        with patch("frappe.db.exists", side_effect=RuntimeError("y" * 400)):
            result = prompts.preview_prompt_template(name="x" * 300)
        self.assertFalse(result["success"])

    def test_log_error_titles_are_short(self):
        from pibiassistant.api.admin import prompts

        logged = []
        with patch("frappe.log_error", side_effect=lambda *a, **kw: logged.append(kw)):
            with patch("frappe.db.exists", side_effect=RuntimeError("z" * 500)):
                prompts.preview_prompt_template(name="x")
        self.assertTrue(logged)
        self.assertLessEqual(len(logged[0]["title"]), 140)
