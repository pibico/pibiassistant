# pibiAssistant - Registration (retired except reset_registration)
# AGPL-3.0 License

"""Registration: RETIRED, except ``reset_registration``.

PA Cloud was retired, so registering, terms, rebinding and diagnostics do
nothing and answer HTTP 410. ``reset_registration`` stays because PA Chat
Settings calls it to clear stale tenant credentials.
"""

import frappe
from frappe import _

from pibiassistant.pibiassistant_chat.api._helpers import _safe_error
from pibiassistant.pibiassistant_chat.cloud_url import get_pa_cloud_url
from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["POST"])
def reset_registration() -> dict:
    """Drop this site's tenant credentials. Clear-only, by design.

    Reset does NOT re-register. Registration requires accepting a specific
    Terms and Conditions version, and terms can only be accepted where they
    are displayed — the SPA onboarding screen. Calling register_with_ar() from
    here could only ever pass a terms_version it had not shown anyone, so this
    hands off instead: clear, mark Not Registered, and let onboarding take over.

    The onward path matters because re-registering against a *different*
    the cloud (a UAT → production cutover) mints a brand-new tenant — the old
    subscription, credits and history stay behind on the old server.

    Returns:
            dict: {"success": bool, "message": str, "previous_tenant_id": str | None}
    """
    # AIDA-M2: the sibling endpoint in page/pa_admin/pa_admin.py uses
    # only_for("System Manager") — match that here so the two admin entry
    # points converge. `has_permission` could green-light custom roles that
    # were granted PA Chat Settings write without intending registration-level
    # authority.
    frappe.only_for("System Manager")

    try:
        from pibiassistant.pibiassistant_chat.tenant_credentials import clear_tenant_secret

        settings = frappe.get_single("PA Chat Settings")
        previous_tenant_id = settings.tenant_id or None

        clear_tenant_secret()
        settings.flags.clear_tenant_secret = True
        settings.tenant_id = None
        settings.tenant_secret = None
        settings.registration_status = "Not Registered"
        settings.save(ignore_permissions=True)

        # Wiping tenant credentials is a privileged, destructive act and leaves
        # no trace on AR (the credentials that would have signed an audit call
        # are exactly what we just destroyed). Record it locally.
        frappe.logger("pao.registration").info(
            f"Registration reset by {frappe.session.user}; "
            f"cleared tenant_id={previous_tenant_id} pointing at {get_pa_cloud_url()}"
        )

        return {
            "success": True,
            "previous_tenant_id": previous_tenant_id,
            "message": _(
                "Registration cleared. Open PA Chat to register this site again — "
                "you will be asked to accept the Terms and Conditions."
            ),
        }

    except Exception as e:
        frappe.log_error(
            title="AIDA Registration Reset Error", message=f"Error resetting registration: {e!s}"
        )
        return {"success": False, "error": _safe_error(e, "AIDA Registration Reset Error")}


# Signup precedes tenant credentials, so referral-code validation must work
# pre-auth. Protected by a 20/minute per-IP rate limit; thin proxy to AR.
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
