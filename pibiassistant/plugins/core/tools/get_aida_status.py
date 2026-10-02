"""
Get AIDA Status Tool for the Core Plugin.
Read-only health snapshot of the AIDA chat; tenant-wide detail is System Manager only.
"""

from typing import Any, Dict

import frappe
from frappe import _

from pibiassistant.core.base_tool import BaseTool


class GetAidaStatus(BaseTool):
    """Report whether AIDA chat is enabled and what it can do for the current user."""

    def __init__(self):
        super().__init__()
        self.name = "get_aida_status"
        self.description = (
            "Health of the AIDA assistant on this site: whether chat is enabled, whether tools and data "
            "changes are on, and the caller's AIDA roles. System Managers also get the last connection "
            "check of the AIDA services and usage statistics. Use it to diagnose why AIDA is unavailable."
        )
        self.requires_permission = None
        self.inputSchema = {"type": "object", "properties": {}}

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        from pibiassistant.pibiassistant_chat.api.chat.aida_tools import aida_status
        from pibiassistant.pibiassistant_chat.gate import is_chat_enabled

        user = frappe.session.user
        snapshot = aida_status(user)
        is_admin = "System Manager" in frappe.get_roles(user)

        result: Dict[str, Any] = {
            "success": True,
            "status": "active" if is_chat_enabled() else "disabled",
            "enabled": is_chat_enabled(),
            "tools_enabled": snapshot["tools_enabled"],
            "write_tools_enabled": snapshot["write_tools_enabled"],
            "user_roles": snapshot["user_roles"],
        }
        if is_admin:
            from pibiassistant.pibiassistant_chat.api.settings.widget import get_aida_status

            result["connections"] = snapshot["connections"]
            result["admin"] = get_aida_status()
        else:
            result["note"] = _("Connection checks and usage statistics are visible to System Managers only.")
        return result


get_aida_status = GetAidaStatus
