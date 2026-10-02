# pibiAssistant - Retired endpoints (Analytics)
# AGPL-3.0 License

"""Analytics: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def get_analytics_data(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_conversation_analytics(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_message_credits(*args, **kwargs):
    retired()
