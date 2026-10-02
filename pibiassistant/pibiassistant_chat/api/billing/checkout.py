# pibiAssistant - Retired endpoints (Billing checkout)
# AGPL-3.0 License

"""Billing checkout: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["POST"])
def initiate_plan_upgrade(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def reauthorize_mandate(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def verify_payment(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def verify_razorpay_payment(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def verify_razorpay_credit_payment(*args, **kwargs):
    retired()
