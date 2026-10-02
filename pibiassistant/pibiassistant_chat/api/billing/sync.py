# pibiAssistant - Retired endpoints (Billing sync)
# AGPL-3.0 License

"""Billing sync: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["POST"])
def sync_subscription_status(*args, **kwargs):
    retired()
