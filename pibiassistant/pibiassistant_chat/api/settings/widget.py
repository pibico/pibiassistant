# pibiAssistant - Widget, Status & Preferences API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Widget customization, copilot status, user preferences, screen-extract fallback."""

from __future__ import annotations

import json

import frappe
from frappe import _

from pibiassistant.pibiassistant_chat.gate import is_chat_enabled

from .._helpers import (
    _require_system_manager,
    _safe_error,
)


@frappe.whitelist(methods=["GET"])
def get_aida_status() -> dict:
    """Get AIDA status for ecosystem integration.

    AIDA-M13: tenant-wide aggregates (``total_conversations``, ``total_users``,
    ``quota_used``, ``plan``) are admin-only signal. Gated to System Manager
    to avoid exposing competitive / social-engineering metadata to every
    authenticated user.
    """
    _require_system_manager()
    try:
        settings = frappe.get_single("PA Chat Settings")

        total_conversations = len(
            frappe.get_all("PA Chat Message", distinct=True, pluck="session_id", limit_page_length=0)
        )

        total_users = frappe.db.count("PA Chat User Preferences")

        from frappe.utils import get_first_day, now

        current_month_start = get_first_day(now())
        monthly_conversations = len(
            frappe.get_all(
                "PA Chat Message",
                filters={"creation": [">=", current_month_start]},
                distinct=True,
                pluck="session_id",
                limit_page_length=0,
            )
        )

        from pibiassistant.pibiassistant_chat.quota_cache import get_quota_snapshot

        snap = get_quota_snapshot()

        chat_enabled = is_chat_enabled()
        return {
            "status": "active"
            if chat_enabled and settings.registration_status == "Registered"
            else "disabled",
            "enabled": chat_enabled,
            "registration_status": settings.registration_status,
            "subscription_plan": snap.get("plan", "Not Registered"),
            "stats": {
                "total_conversations": total_conversations,
                "monthly_conversations": monthly_conversations,
                "total_users": total_users,
                "quota_used": snap.get("quota_used", 0),
                "quota_total": snap.get("quota_total", 0),
                "is_unlimited": snap.get("quota_total", 0) == -1,
            },
            "version": "2.0.0",
        }

    except Exception as e:
        frappe.log_error(title="AIDA Status Error", message=f"Error getting copilot status: {e!s}")
        return {"status": "error", "error": _safe_error(e, "AIDA Status Error")}


@frappe.whitelist(methods=["GET"])
def get_widget_settings() -> dict:
    """Get widget customization settings."""
    try:
        settings = frappe.get_single("PA Chat Settings")

        return {
            "button": {
                "size": 72,
                "icon": "aida",
                "enable_pulse": True,
                "shadow": "0 4px 20px rgba(0,0,0,0.15)",
            },
            "window": {"width": 400, "height": 650, "border_radius": 12, "font_size": "14px"},
            "messages": {},
            "privacy": {
                "enable_dom_extraction": bool(getattr(settings, "enable_dom_extraction", True)),
                "enable_browser_diagnostics": bool(getattr(settings, "enable_browser_diagnostics", True)),
            },
            "custom_css": "",
        }

    except Exception as e:
        frappe.log_error(title="AIDA Widget Error", message=f"Error getting widget settings: {e!s}")
        return {
            "button": {"size": 72, "icon": "aida"},
            "window": {"width": 400, "height": 650},
            "messages": {},
            "custom_css": "",
        }


# Explicit allowlist of user-editable fields on PA Chat User Preferences.
# Must be kept in sync with pa_chat_user_preferences.json. Excludes:
#   - system fields (name, owner, creation, modified, docstatus, idx, parent*)
#   - identity field (user — used as autoname)
#   - privacy/consent flags (privacy_consent_complete — mutated via privacy API only)
# Every entry below corresponds to a DocType Field with read_only=0.
ALLOWED_PREFERENCE_FIELDS: frozenset[str] = frozenset(
    {
        "widget_position",
        "widget_theme",
        "enable_keyboard_shortcut",
        "keyboard_shortcut",
        "show_suggested_prompts",
        "hide_widget",
    }
)


@frappe.whitelist(methods=["POST"])
def update_user_preference(field: str, value: str) -> dict:
    """Update a specific field in the user's AIDA preferences.

    Only fields in ``ALLOWED_PREFERENCE_FIELDS`` may be set through this
    endpoint; attempts to mutate system fields (owner, docstatus, flags,
    parent, user) or privacy/consent flags are rejected.
    """
    # Guard against mass-assignment: check the allowlist BEFORE loading the
    # doc so an attacker can't even cause a write attempt. Raise directly so
    # callers (and tests) receive ValidationError — not a success=False dict.
    if field not in ALLOWED_PREFERENCE_FIELDS:
        frappe.throw(_("Field '{0}' is not updatable via this endpoint").format(field))

    try:
        from pibiassistant.pibiassistant_chat.doctype.pa_chat_user_preferences.pa_chat_user_preferences import (
            PAChatUserPreferences,
        )

        prefs = PAChatUserPreferences.get_or_create_preferences()

        setattr(prefs, field, value)
        prefs.save(ignore_permissions=True)
        return {"success": True, "message": _("Updated {0}").format(field)}

    except frappe.ValidationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(title="AIDA Preference Error", message=f"Error updating user preference: {e!s}")
        return {"success": False, "message": str(e)}


@frappe.whitelist(methods=["GET"])
def extract_screen_content(
    doctype: str | None = None,
    name: str | None = None,
    view_type: str = "Form",
    context: str | None = None,
) -> str:
    """
    DEPRECATED: Basic fallback for server-side content extraction.
    Widget's DOM extraction is the primary method.
    """
    try:
        if isinstance(context, str):
            context = json.loads(context) if context else {}

        if view_type == "Form" and doctype and name:
            return f"Form: {doctype} - {name}"
        elif view_type == "List" and doctype:
            return f"List: {doctype}"
        elif view_type == "Report":
            report_name = context.get("name") if context else name
            return f"Report: {report_name}"
        else:
            return f"Page Type: {view_type}"

    except Exception as e:
        frappe.log_error(title="AIDA Extract Error", message=f"Error in extract_screen_content: {e!s}")
        return "Page view"
