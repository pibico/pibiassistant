# pibiAssistant - Retired endpoints (Connections)
# AGPL-3.0 License

"""Connections: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def list_connections(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def remove_connection(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def set_connection_enabled(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def test_connection(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def set_tool_visibility(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def add_connection(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def begin_connect(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_connect_session(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def commit_connect(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def abandon_connect(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def begin_reauth(*args, **kwargs):
    retired()
