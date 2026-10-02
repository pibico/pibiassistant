# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0-or-later — see <https://www.gnu.org/licenses/>.

import frappe
from frappe import _


@frappe.whitelist(methods=["GET", "POST"])
def get_usage_statistics() -> dict:
    """Get usage statistics for the assistant."""
    from pibiassistant.utils.logger import api_logger
    from pibiassistant.utils.permissions import check_assistant_admin_permission

    if not check_assistant_admin_permission(frappe.session.user):
        api_logger.warning(
            f"Usage statistics denied for non-admin user: {frappe.session.user} "
            f"with roles: {frappe.get_roles(frappe.session.user)}"
        )

    frappe.only_for(["System Manager", "PA Admin"])

    try:
        api_logger.info(f"Usage statistics requested by user: {frappe.session.user}")

        from pibiassistant.utils.usage_statistics import collect_usage_statistics

        return {"success": True, "data": collect_usage_statistics()}

    except Exception as e:
        api_logger.error(f"Error getting usage statistics: {e}")
        return {"success": False, "error": str(e)}


@frappe.whitelist(methods=["GET", "POST"])
def ping() -> dict:
    """Ping endpoint for testing connectivity."""
    from pibiassistant.utils.logger import api_logger
    from pibiassistant.utils.permissions import check_assistant_permission

    try:
        if not check_assistant_permission(frappe.session.user):
            frappe.throw(_("Access denied"))

        return {
            "success": True,
            "message": "pong",
            "timestamp": frappe.utils.now(),
            "user": frappe.session.user,
        }

    except Exception as e:
        api_logger.error(f"Error in ping: {e}")
        return {"success": False, "message": _("Ping failed: {0}").format(str(e))}
