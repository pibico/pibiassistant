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
                    "description": "Specific user to list dashboards for (defaults to current user)",
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
            user = arguments.get("user", frappe.session.user)
            dashboard_type = arguments.get("dashboard_type", "all")
            include_shared = arguments.get("include_shared", True)

            dashboards = []

            # Get user's own dashboards
            own_dashboards = frappe.get_all(
                "Dashboard",
                filters={"owner": user},
                fields=["name", "dashboard_name", "creation", "modified", "module"],
            )

            for dashboard in own_dashboards:
                dashboards.append(
                    {
                        **dashboard,
                        "access_type": "owner",
                        "dashboard_type": "insights"
                        if dashboard.module == "Insights"
                        else "frappe_dashboard",
                    }
                )

            # Get shared dashboards if requested
            if include_shared:
                shared_docs = frappe.get_all(
                    "DocShare",
                    filters={"share_name": user, "share_doctype": "Dashboard", "read": 1},
                    fields=["share_name", "everyone"],
                )

                for shared in shared_docs:
                    try:
                        dashboard_doc = frappe.get_doc("Dashboard", shared.share_name)
                        dashboards.append(
                            {
                                "name": dashboard_doc.name,
                                "dashboard_name": dashboard_doc.dashboard_name,
                                "creation": dashboard_doc.creation,
                                "modified": dashboard_doc.modified,
                                "module": dashboard_doc.module,
                                "access_type": "shared",
                                "dashboard_type": "insights"
                                if dashboard_doc.module == "Insights"
                                else "frappe_dashboard",
                            }
                        )
                    except Exception:
                        continue  # Skip if dashboard doesn't exist or no access

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
