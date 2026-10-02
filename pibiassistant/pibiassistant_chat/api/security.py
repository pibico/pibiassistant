"""Origin challenge callback: RETIRED.

It answered PA Cloud's tenant challenge. PA Cloud was retired, so the dotted path
stays for one release and answers HTTP 410.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep: guest-whitelisted-method
def verify_origin_challenge(*args, **kwargs):
    retired()
