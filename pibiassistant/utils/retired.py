# pibiAssistant - Retired endpoint helper
# AGPL-3.0 License

"""Shared answer for whitelisted endpoints that only ever talked to PA Cloud.

PA Cloud was retired and AIDA runs natively on the AIDA API, so these
endpoints no longer do anything. The dotted paths stay alive for one release
so external mobile / MCP clients get a clear HTTP 410 instead of a 404.
"""

import frappe
from frappe import _


class RetiredEndpointError(frappe.ValidationError):
    """Raised by retired endpoints. Frappe turns ``http_status_code`` into the HTTP status."""

    http_status_code = 410


def retired(*_args, **_kwargs):
    """Answer HTTP 410 Gone with the standard retirement message. Never returns."""
    frappe.throw(
        _("PA Cloud was retired. AIDA now runs natively, this endpoint no longer does anything."),
        exc=RetiredEndpointError,
    )
