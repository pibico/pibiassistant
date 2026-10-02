# pibiAssistant - Retired endpoints (Billing seats)
# AGPL-3.0 License

"""Billing seats: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["POST"])
def add_user_seat(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def verify_seat_payment(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def remove_user_seat(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def preview_seat_charge(*args, **kwargs):
    retired()
