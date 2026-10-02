# pibiAssistant - Retired endpoints (Team users)
# AGPL-3.0 License

"""Team users: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def list_users(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_user_limit_status(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def suspend_user(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def deregister_user(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def add_user(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_available_users(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def set_user_credit_limit(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_my_credit_status(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def invite_user(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def revoke_invite(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def resend_invite(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def list_invites(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_member_audit_log(*args, **kwargs):
    retired()
