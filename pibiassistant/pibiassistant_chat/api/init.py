# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
SPA initialization endpoint.

Combines the access, quota, capabilities, user-auth and conversation-list lookups
into a single request. Everything is answered from this site (AIDA runs natively).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import frappe

from ._helpers import _aida_mode

if TYPE_CHECKING:
    from frappe.model.document import Document


@frappe.whitelist(methods=["POST"])
def initialize_spa() -> dict:
    """
    Combined SPA initialization: access, quota, capabilities, user auth and sessions in one call.

    AIDA runs natively, so every part is answered from this site. When the access gate says
    the user cannot use AIDA only the access block and the fail-safe defaults are returned.

    Returns:
            dict: {
                    "access": { can_use, status, is_admin, user, preferences, ... },
                    "quota": { plan, quota_total, quota_used, quota_remaining, ... },
                    "capabilities": { features: { billing, memory, workflows, ... } },
                    "user_auth": { ready, site_registered, user_registered, ... } | null,
                    "terms": { acceptance_required, can_accept },
                    "onboarding": null,
                    "sessions": [ { session_id, preview, started, last_activity }, ... ],
                    "outstanding": null
            }
    """
    settings = frappe.get_single("PA Chat Settings")
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    is_admin = "System Manager" in user_roles

    access = _build_access(settings, user, user_roles, is_admin)
    access["mcp_endpoint_url"] = ""

    if not _aida_mode() and not access.get("can_use"):
        return {
            "access": access,
            "quota": _build_quota(settings, is_admin),
            "capabilities": _default_capabilities(),
            "user_auth": None,
            "terms": {"acceptance_required": False, "can_accept": is_admin},
            "onboarding": None,
            "sessions": [],
            "outstanding": None,
        }

    return {
        "access": access,
        "quota": {
            "success": True,
            "plan": "AIDA",
            "quota_total": -1,
            "quota_used": 0,
            "quota_remaining": -1,
            "percentage_used": 0,
            "is_unlimited": True,
            "is_admin": is_admin,
            "registration_status": "Registered",
        },
        "capabilities": _aida_capabilities(),
        "user_auth": {
            "success": True,
            "ready": True,
            "site_registered": True,
            "user_registered": True,
            "has_mcp_servers": False,
            "active_server_count": 0,
            "needs_reconnect": False,
        },
        "terms": {"acceptance_required": False, "can_accept": is_admin},
        "onboarding": None,
        "sessions": _fetch_sessions(),
        "outstanding": None,
    }


# ============================================================================
# Helper: Access check (from settings.py:can_use_pao)
# ============================================================================


def _build_access(settings: Document, user: str, user_roles: list[str], is_admin: bool) -> dict:
    """Access-check response for initialize_spa. Delegates to the single
    authoritative gate (can_use_pao) so the boot path and the standalone
    endpoint can never diverge.

    Previously this REIMPLEMENTED the gate and rotted out of sync: it kept the
    old Frappe-role check ("PA User" et al.) after can_use_pao moved to
    authoritative AR membership (_is_pao_member), so real Pending/Active members
    without an assistant role were locked out of the SPA at boot — the exact
    production lockout this collapses.

    can_use_pao reads settings/user/roles from the session itself and returns
    the same shape this used to build (show_widget, is_admin, user,
    pa_cloud_url, can_use, status, reason/preferences). The settings/user/
    user_roles/is_admin params are now unused here; the signature is kept so
    initialize_spa's existing call site (and tests) don't churn. Runs in the
    main thread, so the cloud call _is_pao_member makes (cached 60s) is safe.
    """
    from pibiassistant.pibiassistant_chat.api.settings.access import can_use_pao

    return can_use_pao()


# ============================================================================
# Helper: Quota (from billing.py:get_quota_status)
# ============================================================================


def _build_quota(settings: Document, is_admin: bool) -> dict:
    """Build quota status from Redis quota cache."""
    from pibiassistant.pibiassistant_chat.quota_cache import get_quota_snapshot

    snap = get_quota_snapshot()
    quota_total = snap.get("quota_total", 0)
    quota_used = snap.get("quota_used", 0)
    is_unlimited = quota_total == -1

    if is_unlimited:
        quota_remaining = -1
        percentage_used = 0
    else:
        quota_remaining = max(0, quota_total - quota_used)
        percentage_used = (quota_used / quota_total * 100) if quota_total > 0 else 0

    return {
        "success": True,
        "plan": snap.get("plan", "Free"),
        "quota_total": quota_total,
        "quota_used": quota_used,
        "quota_remaining": quota_remaining,
        "percentage_used": round(percentage_used, 1),
        "is_unlimited": is_unlimited,
        "is_admin": is_admin,
        "registration_status": settings.registration_status,
    }


# ============================================================================
# Helper: Sessions
# ============================================================================


def _fetch_sessions(limit: int = 20) -> list[dict]:
    """Conversation list for the SPA boot payload.

    Delegates to the sidebar's own endpoint so the list the SPA boots with and
    the list it refetches on every ChatView remount are the same list. A private
    copy here once drifted on the ``is_archived`` filter: a page load hydrated
    the sidebar with archived conversations and the first in-app navigation
    replaced them with the filtered list, emptying the sidebar.
    """
    from pibiassistant.pibiassistant_chat.api.chat.sessions import get_user_sessions

    return get_user_sessions(limit=limit)


# ============================================================================
# Helper: Capabilities with caching (5-minute TTL)
# ============================================================================


# ============================================================================
# Helper: Format user auth status
# ============================================================================


# ============================================================================
# Helper: Default capabilities (fail-safe)
# ============================================================================


def _aida_capabilities() -> dict:
    caps = _default_capabilities()
    caps["billing_enabled"] = False
    caps["features"]["billing"] = False
    caps["features"]["mcp_servers"] = False
    caps["version"] = "aida"
    return caps


def _default_capabilities() -> dict:
    """Return safe defaults when AR is unreachable.

    Companion-app features (rag, memory, workflows) default to False
    so the UI hides them rather than showing broken functionality.
    Marketplace defaults: enabled=True (kill-switch off only when AR
    explicitly says so), user_publishing_enabled=False (closed by default).
    """
    return {
        "billing_enabled": True,
        "available_gateways": [],
        "version": "unknown",
        "features": {
            "streaming": True,
            "mcp_servers": True,
            "rag": False,
            "memory": False,
            "billing": True,
            "workflows": False,
            "web_search": False,
        },
        "marketplace": {
            "marketplace_enabled": False,
            "user_publishing_enabled": False,
            "listing_types": [],
        },
    }
