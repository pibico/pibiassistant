# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
List User Dashboards Tool - List all dashboards accessible to current user

List all dashboards accessible to the current user with filtering options.
"""

from typing import Any, Dict, List

import frappe
from frappe import _

from pibiassistant.core.base_tool import BaseTool


class ListUserDashboards(BaseTool):
    """List all dashboards accessible to current user"""

    def __init__(self):
        super().__init__()
        self.name = "list_user_dashboards"
        self.description = "List all dashboards accessible to the current user with filtering options"
        self.requires_permission = None

        self.inputSchema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "string",
                    "description": "User to list dashboards for (defaults to the current user; only System Managers may list another user's)",
                },
                "dashboard_type": {
                    "type": "string",
                    "enum": ["insights", "frappe_dashboard", "all"],
                    "default": "all",
                    "description": "Type of dashboards to list",
                },
                "include_shared": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include dashboards shared with user",
                },
            },
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List accessible dashboards"""
        try:
            session_user = frappe.session.user
            user = arguments.get("user") or session_user
            if user != session_user and "System Manager" not in frappe.get_roles(session_user):
                user = session_user
            dashboard_type = arguments.get("dashboard_type", "all")
            include_shared = arguments.get("include_shared", True)

            fields = ["name", "dashboard_name", "creation", "modified", "module"]

            def _row(dashboard, access_type):
                return {
                    **dashboard,
                    "access_type": access_type,
                    "dashboard_type": "insights" if dashboard.get("module") == "Insights" else "frappe_dashboard",
                }

            dashboards = [
                _row(d, "owner") for d in frappe.get_list("Dashboard", filters={"owner": user}, fields=fields)
            ]
            owned = {d["name"] for d in dashboards}

            if include_shared:
                shares = frappe.get_all(
                    "DocShare",
                    filters={"share_doctype": "Dashboard", "read": 1},
                    or_filters=[["user", "=", user], ["everyone", "=", 1]],
                    pluck="share_name",
                )
                shared_names = [n for n in set(shares) if n not in owned]
                if shared_names:
                    shared = frappe.get_list(
                        "Dashboard", filters={"name": ["in", shared_names]}, fields=fields
                    )
                    dashboards.extend(_row(d, "shared") for d in shared)

            # Filter by dashboard type if specified
            if dashboard_type != "all":
                dashboards = [d for d in dashboards if d["dashboard_type"] == dashboard_type]

            # Sort by modification date (newest first)
            dashboards.sort(key=lambda x: x["modified"], reverse=True)

            return {
                "success": True,
                "dashboards": dashboards,
                "total_count": len(dashboards),
                "user": user,
                "dashboard_type_filter": dashboard_type,
                "includes_shared": include_shared,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
