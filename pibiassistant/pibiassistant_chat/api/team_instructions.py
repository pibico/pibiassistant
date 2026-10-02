# pibiAssistant - Retired endpoints (Shared knowledge)
# AGPL-3.0 License

"""Shared knowledge: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def get_shared_knowledge(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def update_shared_knowledge(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def share_memory_to_knowledge(*args, **kwargs):
    retired()
