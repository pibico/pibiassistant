# pibiAssistant - Retired endpoints (Billing subscription)
# AGPL-3.0 License

"""Billing subscription: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def get_usage_history(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_invoices(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_subscription_status(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_billing_history(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def downgrade_to_free(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def cancel_scheduled_change(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def cancel_subscription(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def reactivate_subscription(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_payment_methods(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_payment_instrument(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def update_payment_method(*args, **kwargs):
    retired()
