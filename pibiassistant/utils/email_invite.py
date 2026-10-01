import frappe
from frappe import _


def send_pa_admin_invite():
    """Welcome every System Manager after installation.

    Unlike every other managed email in the product, this one is sent by the
    customer's own site to its own admins, not by the SaaS server — so it
    must render with plain frappe.sendmail and never depend on
    assistant_runtime being installed here.
    """
    recipients = _get_system_manager_emails()
    if not recipients:
        frappe.log_error("No System Manager users found for PA invite", "PA Invite Hook")
        return

    workspace_url = frappe.utils.get_url("/aida/")
    for recipient in recipients:
        try:
            frappe.sendmail(
                recipients=[recipient],
                subject=_("Your AIDA workspace is ready"),
                template="pa_welcome",
                args={"heading": _("You're all set"), "cta_url": workspace_url},
                delayed=True,
            )
        except Exception:
            frappe.log_error("Failed to send PA welcome email", "PA Invite Hook")


def _get_system_manager_emails():
    """Batch-fetch emails for all enabled System Manager users."""
    system_managers = frappe.get_all(
        "Has Role",
        filters={"role": "System Manager", "parenttype": "User"},
        fields=["parent"],
    )

    if not system_managers:
        return []

    user_names = [sm.parent for sm in system_managers]

    users = frappe.get_all(
        "User",
        filters={"name": ("in", user_names), "enabled": 1},
        fields=["email"],
    )

    return [
        user.email
        for user in users
        if user.email and "@" in user.email and not user.email.endswith("@example.com")
    ]
