# pibiAssistant - Registration (retired)
# AGPL-3.0 License

"""Registration: RETIRED.

PA Cloud was retired, so registering, terms, rebinding, resetting and diagnostics do
nothing and answer HTTP 410. The dotted paths stay for one release.
"""

import frappe

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["POST"])
def reset_registration(*args, **kwargs):
    retired()


# Open to guests before retirement; the flag stays so external clients get the 410.
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
def validate_partner_code(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def register_with_ar(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def get_registration_state(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_plan_comparison(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def complete_email_verification(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def accept_updated_terms(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def request_site_rebind(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def poll_for_rotated_secret(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def run_diagnostics(*args, **kwargs):
    retired()
