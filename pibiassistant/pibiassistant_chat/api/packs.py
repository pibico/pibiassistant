# pibiAssistant - Retired endpoints (Industry packs)
# AGPL-3.0 License

"""Industry packs: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def list_packs(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_pack_contents(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def set_industry(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def set_pack_enabled(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_recommended_pack(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def dismiss_pack_recommendation(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def activate_free_pack(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def toggle_purchased_pack(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def initiate_pack_checkout(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def verify_pack_payment(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def list_pack_purchases(*args, **kwargs):
    retired()
