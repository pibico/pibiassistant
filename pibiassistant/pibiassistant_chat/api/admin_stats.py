# pibiAssistant - Admin dashboard number-card sources.
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Whitelisted methods backing Number Cards on the AIDA Workspace.

Each method returns the shape Frappe's Custom-type Number Card expects:
    {"value": int | float, "fieldtype": str, "route": list}

`fieldtype` is a display hint; `route` is the list-view the user lands on
when they click the card.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import get_first_day, now


def _require_system_manager() -> None:
    """Match the access level of the old pao-admin page."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can view AIDA admin data."), frappe.PermissionError)


@frappe.whitelist(methods=["GET", "POST"])
def active_users_this_month() -> dict[str, Any]:
    """Distinct message authors since the first of the month."""
    _require_system_manager()

    PAChatMessage = frappe.qb.DocType("PA Chat Message")
    row = (
        frappe.qb.from_(PAChatMessage)
        .select(Count(PAChatMessage.owner).distinct().as_("count"))
        .where(PAChatMessage.creation >= get_first_day(now()))
        .run(as_dict=True)
    )
    value = (row[0].get("count") if row else 0) or 0

    return {
        "value": value,
        "fieldtype": "Int",
        "route": ["List", "PA Chat Message"],
    }


@frappe.whitelist(methods=["GET", "POST"])
def token_usage_summary() -> dict[str, Any]:
    """Current-period token usage sourced from the Redis quota cache."""
    _require_system_manager()

    from pibiassistant.pibiassistant_chat.quota_cache import get_quota_snapshot

    try:
        snap = get_quota_snapshot() or {}
    except Exception:
        snap = {}

    return {
        "value": snap.get("quota_used") or 0,
        "fieldtype": "Int",
        "route": ["aida", "billing"],
    }


@frappe.whitelist(methods=["POST"])
def reset_registration(*args, **kwargs):
    """Retired with PA Cloud: answers HTTP 410 (alias of settings.registration.reset_registration)."""
    from pibiassistant.utils.retired import retired

    retired()
