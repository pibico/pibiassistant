# pibiAssistant - Retired endpoints (Marketplace)
# AGPL-3.0 License

"""Marketplace: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def list_listings(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_listing(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def import_listing(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def update_listing(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def delete_listing(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def rate_listing(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def report_listing(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def list_pending_reviews(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def approve_listing(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def reject_listing(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_creator_stats(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def list_my_listings(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def publish_workflow(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def download_listing_as_json(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def check_workflow_update(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def check_all_workflow_updates(*args, **kwargs):
    retired()
