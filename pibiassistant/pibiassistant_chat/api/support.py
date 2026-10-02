# pibiAssistant - Retired endpoints (Support)
# AGPL-3.0 License

"""Support: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def get_environment(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def create_ticket(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def download_ticket_attachment(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def upload_ticket_attachment(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def submit_feedback(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def list_my_tickets(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def list_my_feedback(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def get_ticket_thread(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def reply_to_ticket(*args, **kwargs):
    retired()
