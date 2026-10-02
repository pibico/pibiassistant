# pibiAssistant - Retired endpoints (Billing invoices)
# AGPL-3.0 License

"""Billing invoices: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def download_invoice_pdf(*args, **kwargs):
    retired()
