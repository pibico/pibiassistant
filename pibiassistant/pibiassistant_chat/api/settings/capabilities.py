# pibiAssistant - Retired endpoints (Capabilities and terms)
# AGPL-3.0 License

"""Capabilities and terms: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def get_capabilities(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_ar_terms(*args, **kwargs):
    retired()
