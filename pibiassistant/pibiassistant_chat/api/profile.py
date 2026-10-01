# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""User profile management — view and update AI personalization fields."""

from __future__ import annotations

import frappe
from frappe import _

from ._helpers import _aida_mode
from .auth import _ar_user_id


_LOCAL_PROFILE_KEY = "pibiassistant_profile"
_PROFILE_FIELDS = (
    "display_name",
    "job_title",
    "department",
    "about",
    "custom_instructions",
    "locale",
    "timezone",
)


def _local_profile() -> dict:
    """AIDA mode: the profile lives in the user's defaults, no cloud involved."""
    import json

    try:
        stored = json.loads(frappe.defaults.get_user_default(_LOCAL_PROFILE_KEY) or "{}")
    except (ValueError, TypeError):
        stored = {}
    profile = {k: stored.get(k) for k in _PROFILE_FIELDS}
    profile["display_name"] = profile["display_name"] or frappe.db.get_value(
        "User", frappe.session.user, "full_name"
    )
    profile["locale"] = profile["locale"] or frappe.local.lang
    profile["timezone"] = profile["timezone"] or frappe.db.get_value("User", frappe.session.user, "time_zone")
    return profile


def _update_local_profile(**fields) -> dict:
    import json

    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        return {"success": False, "error": _("No fields to update")}
    try:
        stored = json.loads(frappe.defaults.get_user_default(_LOCAL_PROFILE_KEY) or "{}")
    except (ValueError, TypeError):
        stored = {}
    stored.update(fields)
    frappe.defaults.set_user_default(_LOCAL_PROFILE_KEY, json.dumps(stored))
    return {"success": True, "message": _("Profile updated")}


@frappe.whitelist(methods=["GET"])
def get_profile() -> dict:
    """
    Get the current user's AR profile for AI personalization.

    Returns:
        {
            "display_name": str | None,
            "job_title": str | None,
            "department": str | None,
            "about": str | None,
            "custom_instructions": str | None,
            "locale": str | None,
            "timezone": str | None,
        }
    """
    from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

    client = get_pa_cloud_client()
    if not client:
        if _aida_mode():
            return _local_profile()
        frappe.throw(_("Not connected to the cloud service"))

    user_data = client.get_user(user_id=_ar_user_id(frappe.session.user))
    if not user_data:
        return {
            "display_name": None,
            "job_title": None,
            "department": None,
            "about": None,
            "custom_instructions": None,
            "locale": None,
            "timezone": None,
        }

    return {
        "display_name": user_data.get("display_name"),
        "job_title": user_data.get("job_title"),
        "department": user_data.get("department"),
        "about": user_data.get("about"),
        "custom_instructions": user_data.get("custom_instructions"),
        "locale": user_data.get("locale"),
        "timezone": user_data.get("timezone"),
    }


@frappe.whitelist(methods=["POST"])
def update_profile(
    display_name: str | None = None,
    job_title: str | None = None,
    department: str | None = None,
    about: str | None = None,
    custom_instructions: str | None = None,
    locale: str | None = None,
    timezone: str | None = None,
) -> dict:
    """
    Update the current user's AR profile.

    Only provided (non-None) fields are updated.

    Returns:
        {"success": true, "message": "..."}
    """
    from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

    client = get_pa_cloud_client()
    if not client:
        if _aida_mode():
            return _update_local_profile(
                display_name=display_name,
                job_title=job_title,
                department=department,
                about=about,
                custom_instructions=custom_instructions,
                locale=locale,
                timezone=timezone,
            )
        frappe.throw(_("Not connected to the cloud service"))

    # Build kwargs — only pass fields that were explicitly provided
    kwargs = {}
    if display_name is not None:
        kwargs["display_name"] = display_name
    if job_title is not None:
        kwargs["job_title"] = job_title
    if department is not None:
        kwargs["department"] = department
    if about is not None:
        kwargs["about"] = about
    if custom_instructions is not None:
        kwargs["custom_instructions"] = custom_instructions
    if locale is not None:
        kwargs["locale"] = locale
    if timezone is not None:
        kwargs["timezone"] = timezone

    if not kwargs:
        frappe.throw(_("No fields to update"), frappe.ValidationError)

    return client.update_user(user_id=_ar_user_id(frappe.session.user), **kwargs)
