# pibiAssistant - Subscription Sync API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Subscription sync."""

from __future__ import annotations

import frappe
from frappe import _
from pibiassistant.pibiassistant_chat.api._helpers import _aida_guard, _billing_unavailable_response

from .._helpers import (
    _log,
    _not_registered_error,
    _require_system_manager,
    _safe_error,
)


@frappe.whitelist(methods=["POST"])
@_aida_guard(_billing_unavailable_response)
def sync_subscription_status():
    """
    Sync subscription info from AR.

    Fetches current tenant info including quota usage and updates
    the Redis quota cache.

    Returns:
            dict: Updated subscription info or error
    """
    _require_system_manager()

    try:
        from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client
        from pibiassistant.pibiassistant_chat.quota_cache import (
            get_field,
            set_field,
            update_from_ar,
        )

        client = get_pa_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        info = client.get_tenant_info()

        # Probe billing availability only if not recently checked
        last_sync = get_field("last_sync", "")
        skip_probe = False
        if last_sync:
            from frappe.utils import now, time_diff_in_hours

            skip_probe = time_diff_in_hours(now(), last_sync) < 6

        if skip_probe:
            billing_available = None
        else:
            try:
                billing_available = client.check_billing_available()
            except Exception:
                billing_available = None

        if info:
            subscription = info.get("subscription", {})
            update_from_ar(subscription)

            if info.get("preferred_model"):
                set_field("preferred_model", info["preferred_model"])

            if billing_available is not None:
                set_field("billing_enabled", billing_available)

            return {
                "success": True,
                "subscription": subscription,
                "preferred_model": info.get("preferred_model"),
            }

        return {"error": _("Failed to fetch tenant info")}

    except Exception as e:
        _log(title="AIDA Sync Error", message=f"Error syncing subscription: {e!s}")
        return {"error": _safe_error(e, "AIDA Sync Error")}
