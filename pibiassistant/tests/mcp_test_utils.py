import json
from collections import OrderedDict
from unittest.mock import MagicMock

import frappe
from werkzeug.wrappers import Response

from pibiassistant.mcp.tool_adapter import build_tool_dict


def rpc(server, payload, registry=None, headers=None):
    """Run one JSON-RPC payload through MCPServer.handle; returns (status, parsed body)."""
    request = MagicMock()
    request.method = "POST"
    request.headers = headers or {}
    request.get_json.return_value = payload
    request.get_data.return_value = json.dumps(payload, default=str)
    original = getattr(frappe.local, "request", None)
    frappe.local.request = request
    try:
        response = server.handle(request, Response(), tool_registry=registry)
    finally:
        frappe.local.request = original
    return response.status_code, json.loads(response.get_data(as_text=True))


def registry_with(*tools):
    return OrderedDict((t.name, build_tool_dict(t)) for t in tools)
