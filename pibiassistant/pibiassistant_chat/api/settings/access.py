# pibiAssistant - Access Gate API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Pre-auth gate that decides whether the AIDA widget renders + chat is enabled."""

from __future__ import annotations

import frappe
from frappe import _

from pibiassistant.pibiassistant_chat.api._helpers import _aida_mode
from pibiassistant.pibiassistant_chat.api.auth import _ar_user_id, _is_tenant_owner
from pibiassistant.pibiassistant_chat.cloud_url import get_pa_cloud_url
from pibiassistant.pibiassistant_chat.gate import is_chat_enabled

# Membership-cache TTLs (seconds). A definitive AR answer is trusted for a
# minute; a fail-OPEN grant (transient blip / internal error) is trusted only
# briefly so a real suspension takes effect quickly once AR is reachable again.
_MEMBER_CACHE_TTL = 60
_FAILOPEN_TTL = 5


def _is_pao_member(user: str) -> bool:
    """True if `user` is an Active or Pending AIDA member per AR, cached 60s."""
    cache_key = f"aida_member:{user}"
    cached = frappe.cache.get_value(cache_key, expires=True)
    if cached is not None:
        return cached in (True, "1", 1)

    is_member = True  # default fail-open until we get a definitive answer
    definitive = False  # True only when AR gave us a real yes/no (not a fail-open)
    try:
        from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

        client = get_pa_cloud_client()
        if not client:
            # Unregistered site → not a member (the gate handles this earlier too).
            is_member = False
            definitive = True
        else:
            # AR keys AR Tenant Users by email — query with the normalized
            # identity, not the raw Frappe username (else the Administrator
            # owner, whose seat is keyed by email, reads as a non-member).
            result = client.get_user_auth_status(user_id=_ar_user_id(user)) or {}
            if result.get("_ar_unreachable"):
                # Transient AR failure — trust the session, don't lock out.
                is_member = True
            else:
                # AR answered authoritatively: gate on the real AR Tenant User status.
                is_member = bool(result.get("user_exists")) and result.get("user_status") in (
                    "Active",
                    "Pending",
                )
                definitive = True
    except Exception:
        # Unexpected internal error → fail OPEN; don't crash or wall off the gate.
        # (Definitive AR "no" answers are handled above and stay fail-CLOSED.)
        frappe.log_error(title="AIDA membership check failed")
        is_member = True

    ttl = _MEMBER_CACHE_TTL if definitive else _FAILOPEN_TTL
    frappe.cache.set_value(cache_key, "1" if is_member else "0", expires_in_sec=ttl)
    return is_member


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

        settings = frappe.get_single("PA Chat Settings")
        user = frappe.session.user
        user_roles = frappe.get_roles(user)
        is_admin = "System Manager" in user_roles or user == "Administrator"

        # Computed once, here, so every return path below carries it via
        # base_response — the field the browser diagnostics recorder's kill
        # switch reads BEFORE any launcher-visibility decision, so a
        # non-member or an admin-disabled user still gets the operator's real
        # setting instead of running the recorder forever unreachable.
        enable_browser_diagnostics = bool(getattr(settings, "enable_browser_diagnostics", True))

        # Master gate already passed above — widget can render
        base_response = {
            "show_widget": True,
            "is_admin": is_admin,
            "user": user,
            "pa_cloud_url": get_pa_cloud_url(),
            "enable_browser_diagnostics": enable_browser_diagnostics,
        }

        # Check AR registration status FIRST
        if settings.registration_status != "Registered":
            return {
                **base_response,
                "can_use": False,
                "status": "not_registered",
                "reason": _("AIDA needs to be connected to the cloud service"),
            }

        # Verify tenant credentials are actually present
        # This catches edge cases where status is "Registered" but credentials are missing
        if not settings.tenant_id or not settings.tenant_secret:
            return {
                **base_response,
                "can_use": False,
                "status": "not_registered",
                "reason": _("AIDA registration is incomplete. Please re-register."),
            }

        # Access follows AIDA membership (a seat), not Frappe role.
        has_access = _is_pao_member(user)
        if not has_access:
            # The tenant owner has no seat on first login (registration creates
            # the tenant, not a seat). Send them to the Connect flow
            # (ready + needs_user_setup) instead of the "ask your admin"
            # AccessDenied screen, so they can self-provision. A plain
            # non-member is still routed to AccessDenied (no_role).
            if _is_tenant_owner(_ar_user_id(user)):
                return {
                    **base_response,
                    "show_widget": True,
                    "can_use": False,
                    "needs_user_setup": True,
                    "status": "ready",
                }
            return {
                **base_response,
                "show_widget": is_admin,
                "can_use": False,
                "status": "no_role",
                "reason": _(
                    "Your administrator needs to add you to AIDA. Please ask them to add you from Settings > Users."
                ),
            }

        # Get or create user preferences (UI settings only)
        from pibiassistant.pibiassistant_chat.doctype.pa_chat_user_preferences.pa_chat_user_preferences import (
            PAChatUserPreferences,
        )

        prefs = PAChatUserPreferences.get_or_create_preferences()

        # Calculate quota remaining from cached subscription info
        from pibiassistant.pibiassistant_chat.quota_cache import get_quota_snapshot

        snap = get_quota_snapshot()
        quota_total = snap.get("quota_total", 0)
        quota_used = snap.get("quota_used", 0)
        is_unlimited = quota_total == -1

        if is_unlimited:
            quota_remaining = -1
        else:
            quota_remaining = quota_total - quota_used

            # If locally exhausted but cache is stale, sync before reporting exhaustion
            last_sync = snap.get("last_sync", "")
            if quota_remaining <= 0 and last_sync:
                from frappe.utils import now, time_diff_in_hours

                hours_since_sync = time_diff_in_hours(now(), last_sync)
                if hours_since_sync > 1:
                    from ..billing import (
                        sync_subscription_status,
                    )

                    sync_subscription_status()
                    snap = get_quota_snapshot()
                    quota_total = snap.get("quota_total", 0)
                    quota_used = snap.get("quota_used", 0)
                    is_unlimited = quota_total == -1
                    quota_remaining = -1 if is_unlimited else max(0, quota_total - quota_used)

        return {
            **base_response,
            "can_use": True,
            "status": "ready",
            "preferences": {
                "keyboard_shortcut": (
                    prefs.keyboard_shortcut
                    if prefs.keyboard_shortcut and prefs.keyboard_shortcut != "Ctrl+K"
                    else "Ctrl+Shift+K"
                )
                if prefs.enable_keyboard_shortcut
                else None,
                "show_suggested_prompts": prefs.show_suggested_prompts,
                "hide_widget": int(getattr(prefs, "hide_widget", 0) or 0),
                "privacy_consent_complete": bool(getattr(prefs, "privacy_consent_complete", 0)),
                "subscription_plan": snap.get("plan", "Free"),
                "quota_total": quota_total,
                "quota_used": quota_used,
                "quota_remaining": quota_remaining,
                "is_unlimited": is_unlimited,
            },
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
