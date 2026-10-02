# pibiAssistant - Access Gate API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Pre-auth gate that decides whether the AIDA widget renders + chat is enabled."""

from __future__ import annotations

import frappe
from frappe import _

from pibiassistant.pibiassistant_chat.api._helpers import _aida_mode
from pibiassistant.pibiassistant_chat.gate import is_chat_enabled

# Called on every page load to decide whether to render the chat widget.
# Must work pre-auth so guests see an onboarding CTA; returns only a
# boolean + a public reason string, never tenant data or tokens.
@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep: guest-whitelisted-method
def can_use_pao() -> dict:
    """Check if the current user can use AIDA."""
    try:
        # Master gate: PA-level enable_pa_chat (PA Core Settings).
        # When off, the widget is fully hidden and no further checks run.
        # This is what allows runtime toggling without a worker restart.
        #
        # With chat off, diagnostics is unconditionally False regardless of
        # the per-feature flag: there is no assistant to consume the buffers,
        # so recording would be pure cost with nothing to show for it.
        if not is_chat_enabled():
            return {
                "show_widget": False,
                "can_use": False,
                "status": "chat_module_disabled",
                "is_admin": "System Manager" in frappe.get_roles(frappe.session.user),
                "user": frappe.session.user,
                "enable_browser_diagnostics": False,
            }

        # AIDA mode: when aida_api_key is configured, bypass cloud registration
        if _aida_mode():
            user = frappe.session.user
            if user == "Guest":
                return {
                    "show_widget": False,
                    "can_use": False,
                    "status": "not_logged_in",
                    "is_admin": False,
                    "user": user,
                    "enable_browser_diagnostics": False,
                }
            user_roles = frappe.get_roles(user)
            is_admin = "System Manager" in user_roles or user == "Administrator"
            has_role = "PA User" in user_roles or "PA Admin" in user_roles or is_admin
            return {
                "show_widget": has_role,
                "can_use": has_role,
                "status": "ready" if has_role else "no_role",
                "is_admin": is_admin,
                "user": user,
                "pa_cloud_url": "",
                "enable_browser_diagnostics": False,
                "preferences": {"quota_used": 0, "quota_limit": 999999,
                                "privacy_consent_complete": True},
            }

        # No AIDA API key: nothing to talk to. The widget routes status "not_registered"
        # to its onboarding CTA.
        user = frappe.session.user
        user_roles = frappe.get_roles(user)
        is_admin = "System Manager" in user_roles or user == "Administrator"
        settings = frappe.get_single("PA Chat Settings")
        return {
            "show_widget": True,
            "is_admin": is_admin,
            "user": user,
            "pa_cloud_url": "",
            "enable_browser_diagnostics": bool(getattr(settings, "enable_browser_diagnostics", True)),
            "can_use": False,
            "status": "not_registered",
            "reason": _("AIDA is not configured on this site."),
        }

    except Exception as e:
        frappe.log_error(title="AIDA API Error", message=f"Error in can_use_pao: {e!s}")
        return {
            "show_widget": False,  # Don't show widget on error
            "can_use": False,
            "status": "error",
            "is_admin": False,
            "pa_cloud_url": "",  # Empty - widget won't show anyway on error
            "reason": _("Error checking AIDA availability"),
            # No enable_browser_diagnostics key here, deliberately: its
            # ABSENCE is what tells the client this is an inferred fail-open
            # value, not a real answer to persist. Returning True would
            # overwrite a genuine persisted "off" from an earlier, successful
            # response — the widget.js defect this same fix closed, one
            # layer up.
        }
