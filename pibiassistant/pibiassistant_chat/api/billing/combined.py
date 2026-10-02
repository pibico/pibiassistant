# pibiAssistant - Retired endpoints (Billing page data)
# AGPL-3.0 License

"""Billing page data: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def get_billing_page_data(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_billing_details(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def save_billing_details(*args, **kwargs):
    retired()
