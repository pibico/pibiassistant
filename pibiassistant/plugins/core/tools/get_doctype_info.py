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
Get DocType Info Tool for Core Plugin.
Get DocType metadata and field information.
"""

from typing import Any, Dict

import frappe
from frappe import _

from pibiassistant.core.base_tool import BaseTool


class GetDoctypeInfo(BaseTool):
    """
    Tool for getting DocType metadata and field information.

    Provides capabilities for:
    - DocType metadata retrieval
    - Field information and structure
    - Permission and workflow details
    """

    def __init__(self):
        super().__init__()
        self.name = "get_doctype_info"
        self.description = "Get DocType metadata and field information"
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {"doctype": {"type": "string", "description": "DocType name"}},
            "required": ["doctype"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute DocType info retrieval"""
        try:
            # Import the metadata implementation
            from .metadata_tools import MetadataTools

            # Execute metadata retrieval using existing implementation
            return MetadataTools.get_doctype_metadata(doctype=arguments.get("doctype"))

        except Exception as e:
            frappe.log_error(
                title=_("Get DocType Info Error"), message=f"Error getting DocType info: {str(e)}"
            )

            return {"success": False, "error": str(e)}


# Make sure class name matches file name for discovery
get_doctype_info = GetDoctypeInfo
