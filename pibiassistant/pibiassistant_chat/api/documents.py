# pibiAssistant - Retired endpoints (Knowledge-base documents)
# AGPL-3.0 License

"""Knowledge-base documents: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def list_documents(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_document(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def list_chunks(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def upload_document(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def delete_document(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def update_document_access(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_document_content(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_storage_info(*args, **kwargs):
    retired()
