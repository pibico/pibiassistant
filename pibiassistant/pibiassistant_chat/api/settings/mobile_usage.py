# pibiAssistant - Retired endpoints (Mobile usage)
# AGPL-3.0 License

"""Mobile usage: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def get_usage_stats(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_usage_history(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_subscription_info(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_model_usage(*args, **kwargs):
    retired()
