# pibiAssistant - Retired endpoints (Memories)
# AGPL-3.0 License

"""Memories: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def list_memories(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def delete_memory(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def update_memory(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def delete_all_memories(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_memory_stats(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_memory_summary(*args, **kwargs):
    retired()
