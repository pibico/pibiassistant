# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0-or-later — see <https://www.gnu.org/licenses/>.

"""Usage statistics shared by the admin and assistant API endpoints."""

import frappe

from pibiassistant.utils.logger import api_logger


def collect_usage_statistics() -> dict:
    """Audit-log counts, loaded tool counts and recent activity (no permission checks)."""
    today = frappe.utils.today()
    week_start = frappe.utils.add_days(today, -7)

    try:
        total_audit = frappe.db.count("PA Audit Log") or 0
        today_audit = frappe.db.count("PA Audit Log", {"creation": (">=", today)}) or 0
        week_audit = frappe.db.count("PA Audit Log", {"creation": (">=", week_start)}) or 0
    except Exception as e:
        api_logger.warning(f"Audit stats error: {e}")
        total_audit = today_audit = week_audit = 0

    try:
        from pibiassistant.utils.plugin_manager import get_plugin_manager

        total_tools = len(get_plugin_manager().get_all_tools())
    except Exception as e:
        api_logger.warning(f"Tool stats error: {e}")
        total_tools = 0

    try:
        recent_activity = (
            frappe.db.get_list(
                "PA Audit Log",
                fields=["action", "tool_name", "user", "status", "timestamp"],
                order_by="timestamp desc",
                limit=10,
            )
            or []
        )
    except Exception as e:
        api_logger.warning(f"Recent activity error: {e}")
        recent_activity = []

    # Connection activity is not tracked separately; audit log activity is its proxy.
    counts = {"total": total_audit, "today": today_audit, "this_week": week_audit}
    return {
        "connections": dict(counts),
        "audit_logs": dict(counts),
        "tools": {"total": total_tools, "enabled": total_tools},
        "recent_activity": recent_activity,
    }
