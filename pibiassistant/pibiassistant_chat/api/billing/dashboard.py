# pibiAssistant - Retired endpoints (Billing dashboard)
# AGPL-3.0 License

"""Billing dashboard: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def get_billing_dashboard(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_plan_options(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_available_gateways(*args, **kwargs):
    retired()
