# pibiAssistant - Retired endpoints (Streaming events)
# AGPL-3.0 License

"""Streaming events: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def get_message_events(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_tool_stats(*args, **kwargs):
    retired()
