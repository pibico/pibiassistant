# pibiAssistant - Retired endpoints (Workflow triggers)
# AGPL-3.0 License

"""Workflow triggers: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def list_triggers(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def create_trigger(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def update_trigger(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def delete_trigger(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def toggle_trigger(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_doctype_fields(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def list_filterable_doctypes(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_trigger_log(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def test_trigger(*args, **kwargs):
    retired()

