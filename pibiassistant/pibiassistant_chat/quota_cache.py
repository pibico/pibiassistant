# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Usage quota snapshot.

AIDA runs natively and has no seat or credit quota, so the snapshot is a constant that
never blocks anyone. Callers (SPA boot, widget status, admin cards) keep reading the
same shape, so the response format of those endpoints is unchanged.
"""

from __future__ import annotations


def get_quota_snapshot() -> dict:
    """Return the quota state: unlimited, nothing used.

    Returns:
            dict: {
                    "plan": str,
                    "quota_total": int (-1 means unlimited),
                    "quota_used": int,
                    "last_sync": str,
                    "billing_enabled": bool,
                    "preferred_model": str,
            }
    """
    return {
        "plan": "Unknown",
        "quota_total": -1,
        "quota_used": 0,
        "last_sync": "",
        "billing_enabled": True,
        "preferred_model": "",
    }
