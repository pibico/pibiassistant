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

from typing import Any, Dict, List

import frappe


class ToolRegistry:
    """Registry for assistant tools"""

    @staticmethod
    def get_tools() -> List[Dict[str, Any]]:
        """Return a list of available assistant tools"""
        return [
            {
                "name": "create_document",
                "description": "Create a new Frappe document",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doctype": {"type": "string", "description": "Document type to create"},
                        "data": {"type": "object", "description": "Document data"},
                        "submit": {"type": "boolean", "default": False},
                    },
                    "required": ["doctype", "data"],
                },
            },
            {
                "name": "get_document",
                "description": "Retrieve a specific document",
                "inputSchema": {
                    "type": "object",
                    "properties": {"doctype": {"type": "string"}, "name": {"type": "string"}},
                    "required": ["doctype", "name"],
                },
            },
            {
                "name": "update_document",
                "description": "Update an existing document",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doctype": {"type": "string"},
                        "name": {"type": "string"},
                        "data": {"type": "object"},
                    },
                    "required": ["doctype", "name", "data"],
                },
            },
            {
                "name": "search_documents",
                "description": "Search documents with filters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doctype": {"type": "string"},
                        "filters": {"type": "object", "default": {}},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["doctype"],
                },
            },
        ]

    @staticmethod
    def create_document(doctype: str, data: Dict[str, Any], submit: bool = False) -> Dict[str, Any]:
        """Create a new Frappe document"""
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' does not exist"}

            if not frappe.has_permission(doctype, "create"):
                return {"success": False, "error": f"No create permission for {doctype}"}

            doc = frappe.get_doc(data)
            doc.doctype = doctype
            doc.insert()

            if submit and hasattr(doc, "submit") and doc.docstatus == 0:
                doc.submit()

            return {
                "success": True,
                "name": doc.name,
                "doctype": doctype,
                "status": "Submitted" if submit else "Draft",
            }

        except Exception as e:
            frappe.log_error(f"Create Document Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_document(doctype: str, name: str) -> Dict[str, Any]:
        """Retrieve a specific document"""
        try:
            doc = frappe.get_doc(doctype, name)
            return {"success": True, "data": doc.as_dict()}
        except frappe.DoesNotExistError:
            return {"success": False, "error": f"Document '{name}' not found"}
        except Exception as e:
            frappe.log_error(f"Get Document Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_document(doctype: str, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing document"""
        try:
            doc = frappe.get_doc(doctype, name)
            for key, value in data.items():
                setattr(doc, key, value)
            doc.save()
            return {"success": True, "name": doc.name, "doctype": doctype}
        except frappe.DoesNotExistError:
            return {"success": False, "error": f"Document '{name}' not found"}
        except Exception as e:
            frappe.log_error(f"Update Document Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def search_documents(
        doctype: str, filters: Dict[str, Any] = None, fields: List[str] = None, limit: int = 20
    ) -> Dict[str, Any]:
        """Search documents with filters"""
        try:
            filters = filters or {}
            docs = frappe.get_all(doctype, filters=filters, fields=fields or ["*"], limit=limit)
            return {"success": True, "data": docs}
        except Exception as e:
            frappe.log_error(f"Search Documents Error: {str(e)}")
            return {"success": False, "error": str(e)}
