# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
Redis-backed quota cache for subscription data.

Replaces the former PA Chat Settings DocType fields (subscription_plan,
subscription_quota, subscription_used, last_sync, billing_enabled,
preferred_model) with a lightweight Redis cache.

Why Redis instead of DocType fields:
- Atomic increment for quota_used (no ORM save contention)
- Sub-millisecond reads for hot paths (stream_complete events)
- Naturally ephemeral — the 6-hour scheduled sync corrects drift
- Cold-start self-healing via seed_from_ar()
"""

from __future__ import annotations

import frappe

CACHE_KEY = "pao_quota_cache"
CACHE_TTL = 86400  # 24 hours


def get_quota_snapshot() -> dict:
    """Read the full quota state from cache.

    On cache miss (cold start / Redis restart), seeds unlimited defaults.

    Returns:
            dict: {
                    "plan": str,
                    "quota_total": int,
                    "quota_used": int,
                    "last_sync": str (ISO datetime),
                    "billing_enabled": bool,
                    "preferred_model": str,
            }
    """
    snap = frappe.cache.get_value(CACHE_KEY, expires=True)
    if snap:
        return snap

    return seed_from_ar()


def set_field(field: str, value) -> None:
    """Set a single field in the cache."""
    snap = get_quota_snapshot()
    snap[field] = value
    _write(snap)


def get_field(field: str, default=None):
    """Get a single field from the cache."""
    snap = get_quota_snapshot()
    return snap.get(field, default)


def seed_from_ar() -> dict:
    """Cold-start handler: write unlimited defaults so users are never blocked.

    The name is kept for existing callers; there is no remote quota source any more.
    """
    defaults = _safe_defaults()
    _write(defaults)
    return defaults


def clear() -> None:
    """Clear the quota cache. Used in tests."""
    frappe.cache.delete_value(CACHE_KEY)


def _write(snap: dict) -> None:
    """Write snapshot to Redis with TTL."""
    frappe.cache.set_value(CACHE_KEY, snap, expires_in_sec=CACHE_TTL)


def _safe_defaults() -> dict:
    """Safe defaults when AR is unreachable on cold start."""
    return {
        "plan": "Unknown",
        "quota_total": -1,  # Unlimited — don't block users
        "quota_used": 0,
        "last_sync": "",
        "billing_enabled": True,
        "preferred_model": "",
    }
