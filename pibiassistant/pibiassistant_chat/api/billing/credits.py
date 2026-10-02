# pibiAssistant - Retired endpoints (Billing credits)
# AGPL-3.0 License

"""Billing credits: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def get_credit_balance(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def purchase_credits(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_expiring_credits(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_consumption_breakdown(*args, **kwargs):
    retired()
