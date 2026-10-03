"""MCP polish: titles and honest annotations, bare search/fetch results for ChatGPT, compact text with
structuredContent, and trimming of oversized results."""

import json
import unittest
from unittest import mock

import frappe

from pibiassistant.mcp import server as mcp_server
from pibiassistant.mcp.server import MCPServer
from pibiassistant.utils.result_limits import fit_result
from pibiassistant.utils.tool_category_detector import (
    TOOL_ANNOTATION_OVERRIDES,
    tool_annotations,
    tool_title,
)


def _call(server, registry, name, arguments):
    return server._handle_tools_call({"name": name, "arguments": arguments}, registry)


def _registry_with(name, fn):
    return {name: {"name": name, "description": "d", "inputSchema": {"type": "object"}, "fn": fn}}


class TestAnnotationsAndTitles(unittest.TestCase):
    def test_titles(self):
        self.assertEqual(tool_title("create_document"), "Create document")
        self.assertEqual(tool_title("search"), "Search")
        self.assertEqual(tool_title("run_python_code"), "Run Python code")

    def test_plain_writes_are_not_destructive_and_stay_on_the_site(self):
        hints = tool_annotations("create_document", "write")
        self.assertEqual(hints["readOnlyHint"], False)
        self.assertEqual(hints["destructiveHint"], False)
        self.assertEqual(hints["openWorldHint"], False)
        self.assertEqual(hints["title"], "Create document")

    def test_overrides(self):
        self.assertTrue(tool_annotations("cancel_document", "write")["destructiveHint"])
        self.assertTrue(tool_annotations("update_document", "write")["idempotentHint"])
        self.assertTrue(tool_annotations("send_email", "write")["openWorldHint"])
        self.assertTrue(tool_annotations("delete_document", "privileged")["destructiveHint"])
        self.assertTrue(tool_annotations("get_document", "read_only")["readOnlyHint"])
        self.assertNotIn("destructiveHint", tool_annotations("get_document", "read_only"))

    def test_unknown_category_gives_no_hints(self):
        self.assertEqual(tool_annotations("x", "weird"), {})

    def test_overrides_only_name_real_keys(self):
        allowed = {"idempotentHint", "destructiveHint", "openWorldHint", "readOnlyHint"}
        for name, hints in TOOL_ANNOTATION_OVERRIDES.items():
            self.assertLessEqual(set(hints), allowed, name)

    def test_live_tools_list_carries_title_and_annotations(self):
        from pibiassistant.api.pa_endpoint import _build_tool_registry

        frappe.set_user("Administrator")
        registry = _build_tool_registry()
        tools = {t["name"]: t for t in MCPServer()._handle_tools_list({}, registry)["tools"]}
        self.assertTrue(tools)
        for name, tool in tools.items():
            self.assertTrue(tool.get("title"), name)
            self.assertEqual(tool["annotations"]["title"], tool["title"], name)
            self.assertIn("openWorldHint", tool["annotations"], name)
        self.assertTrue(tools["list_documents"]["annotations"]["readOnlyHint"])
        self.assertFalse(tools["create_document"]["annotations"]["destructiveHint"])
        self.assertTrue(tools["cancel_document"]["annotations"]["destructiveHint"])


class TestInitialize(unittest.TestCase):
    def test_server_info_and_instructions(self):
        result = MCPServer()._handle_initialize({"protocolVersion": "2025-06-18"})
        self.assertEqual(result["serverInfo"]["title"], "AIDA by pibiCo")
        self.assertIn("permissions of the user", result["instructions"])
        self.assertEqual(result["protocolVersion"], "2025-06-18")


class TestToolResults(unittest.TestCase):
    def setUp(self):
        self.server = MCPServer()

    def test_search_and_fetch_are_bare_for_chatgpt(self):
        registry = _registry_with(
            "search", lambda **a: {"success": True, "result": {"results": [{"id": "A/1", "title": "t", "url": "u"}]}, "execution_time": 0.1}
        )
        out = _call(self.server, registry, "search", {})
        body = json.loads(out["content"][0]["text"])
        self.assertEqual(list(body), ["results"])
        self.assertEqual(out["structuredContent"], body)
        self.assertFalse(out["isError"])

        registry = _registry_with(
            "fetch", lambda **a: {"success": True, "result": {"id": "A/1", "title": "t", "text": "hola", "url": "u", "metadata": {}}}
        )
        body = json.loads(_call(self.server, registry, "fetch", {})["content"][0]["text"])
        self.assertEqual(body["text"], "hola")
        self.assertNotIn("success", body)

    def test_other_tools_keep_their_envelope(self):
        registry = _registry_with("list_documents", lambda **a: {"success": True, "result": {"data": [1]}, "execution_time": 0.1})
        body = json.loads(_call(self.server, registry, "list_documents", {})["content"][0]["text"])
        self.assertTrue(body["success"])
        self.assertEqual(body["result"], {"data": [1]})

    def test_failed_tool_is_marked_and_search_error_is_not(self):
        registry = _registry_with("get_document", lambda **a: {"success": False, "error": "no"})
        self.assertTrue(_call(self.server, registry, "get_document", {})["isError"])

    def test_text_is_compact_with_structured_content(self):
        registry = _registry_with("get_document", lambda **a: {"success": True, "result": {"name": "X", "n": 1}})
        out = _call(self.server, registry, "get_document", {})
        text = out["content"][0]["text"]
        self.assertNotIn("\n", text)
        self.assertNotIn(": ", text)
        self.assertEqual(out["structuredContent"], json.loads(text))

    def test_big_result_is_trimmed_without_structured_content(self):
        rows = [{"name": f"ROW-{i}", "note": "x" * 200} for i in range(3000)]
        registry = _registry_with("list_documents", lambda **a: {"success": True, "result": {"data": rows}})
        with mock.patch.dict(frappe.local.conf, {"mcp_max_result_chars": 20000}):
            out = _call(self.server, registry, "list_documents", {})
        text = out["content"][0]["text"]
        self.assertLessEqual(len(text), 20000)
        body = json.loads(text)
        self.assertTrue(body["truncated"])
        self.assertEqual(body["total"], 3000)
        self.assertLess(body["rows_shown"], 3000)
        self.assertIn("narrow", body["hint"])
        self.assertNotIn("structuredContent", out)

    def test_medium_payload_skips_structured_content(self):
        rows = [{"name": f"ROW-{i}", "note": "y" * 100} for i in range(600)]
        registry = _registry_with("list_documents", lambda **a: {"success": True, "result": {"data": rows}})
        out = _call(self.server, registry, "list_documents", {})
        self.assertGreater(len(out["content"][0]["text"]), mcp_server.MAX_STRUCTURED_CHARS)
        self.assertNotIn("structuredContent", out)
        self.assertNotIn("truncated", json.loads(out["content"][0]["text"]))

    def test_fit_result_helper_is_shared(self):
        rows = [{"i": i, "p": "z" * 50} for i in range(500)]
        out = json.loads(fit_result(json.dumps({"data": rows}), 5000))
        self.assertTrue(out["truncated"])
        self.assertLessEqual(len(json.dumps(out)), 5000)
