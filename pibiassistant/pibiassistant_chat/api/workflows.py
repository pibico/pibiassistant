# pibiAssistant - Retired endpoints (Workflows)
# AGPL-3.0 License

"""Workflows: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def list_workflows(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def create_workflow(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_workflow(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def update_workflow(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def delete_workflow(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def execute_workflow(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def cancel_workflow_run(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_workflow_run(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def list_workflow_runs(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_workflow_audit_summary(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def set_workflow_schedule(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def validate_workflow_graph(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def test_workflow_node(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def run_workflow_node(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def list_user_tools(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def resolve_workflow_tools(*args, **kwargs):
    retired()
