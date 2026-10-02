# pibiAssistant - Retired endpoints (Routing preferences)
# AGPL-3.0 License

"""Routing preferences: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def list_routing_preferences(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def create_routing_preference(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def set_routing_preference_status(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def set_routing_preference_mode(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def delete_routing_preference(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def forecast_routing_preference(*args, **kwargs):
    retired()
