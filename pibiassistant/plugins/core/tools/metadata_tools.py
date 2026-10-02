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
from frappe import _

from pibiassistant.plugins.query_errors import log_failure

LAYOUT_FIELDTYPES = frozenset({"Section Break", "Column Break", "Tab Break", "HTML", "Heading", "Fold", "Button"})
TABLE_FIELDTYPES = frozenset({"Table", "Table MultiSelect"})
OPTIONS_MAX = 120

DOCTYPE_INFO_PROPERTIES = {
    "doctype": {"type": "string", "description": "DocType name"},
    "child_table": {
        "type": "string",
        "description": "Child table fieldname (e.g. 'items'): return that table's full field metadata only.",
    },
    "fieldnames": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Return full metadata (label, description, depends_on...) only for these fields, in the parent and its child tables.",
    },
    "include_layout": {
        "type": "boolean",
        "default": False,
        "description": "Return the verbose legacy shape with layout breaks and hidden fields (large).",
    },
}


class MetadataTools:
    """assistant tools for Frappe metadata operations"""

    @staticmethod
    def get_tools() -> List[Dict]:
        """Return list of metadata-related assistant tools"""
        return [
            {
                "name": "get_doctype_info",
                "description": "Get DocType metadata and field information",
                "inputSchema": {
                    "type": "object",
                    "properties": DOCTYPE_INFO_PROPERTIES,
                    "required": ["doctype"],
                },
            },
            {
                "name": "metadata_list_doctypes",
                "description": "List all available DocTypes",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "module": {"type": "string", "description": "Filter by module"},
                        "custom_only": {
                            "type": "boolean",
                            "default": False,
                            "description": "Show only custom DocTypes",
                        },
                    },
                },
            },
            {
                "name": "metadata_permissions",
                "description": "Get permission information for a DocType",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doctype": {"type": "string", "description": "DocType name"},
                        "user": {"type": "string", "description": "User to check permissions for (optional)"},
                    },
                    "required": ["doctype"],
                },
            },
            {
                "name": "metadata_workflow",
                "description": "Get workflow information for a DocType",
                "inputSchema": {
                    "type": "object",
                    "properties": {"doctype": {"type": "string", "description": "DocType name"}},
                    "required": ["doctype"],
                },
            },
        ]

    @staticmethod
    def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a metadata tool with given arguments"""
        if tool_name == "get_doctype_info":
            return MetadataTools.get_doctype_metadata(**arguments)
        elif tool_name == "metadata_list_doctypes":
            return MetadataTools.list_doctypes(**arguments)
        elif tool_name == "metadata_permissions":
            return MetadataTools.get_permissions(**arguments)
        elif tool_name == "metadata_workflow":
            return MetadataTools.get_workflow(**arguments)
        else:
            raise Exception(f"Unknown metadata tool: {tool_name}")

    @staticmethod
    def _serialize_field(field) -> Dict[str, Any]:
        """Serialize a DocField row into the shape returned by get_doctype_metadata."""
        return {
            "fieldname": field.fieldname,
            "label": field.label,
            "fieldtype": field.fieldtype,
            "options": field.options,
            "reqd": field.reqd,
            "read_only": field.read_only,
            "hidden": field.hidden,
            "default": field.default,
            "description": field.description,
        }

    @staticmethod
    def _compact_field(field) -> str:
        """One line per field: 'fieldname: Fieldtype>options *' (* = required)."""
        entry = f"{field.fieldname}: {field.fieldtype}"
        options = (field.options or "").strip()
        if options:
            options = "|".join(options.split("\n"))
            entry += f">{options[:OPTIONS_MAX]}"
        if field.reqd:
            entry += " *"
        if field.default and str(field.default) not in ("0", "1"):
            entry += f" default={str(field.default)[:40]}"
        return entry

    @staticmethod
    def _data_fields(meta) -> list:
        """Fields a caller can actually fill: no layout breaks, hidden or read-only fields, or tables."""
        return [
            f
            for f in meta.fields
            if f.fieldtype not in LAYOUT_FIELDTYPES
            and f.fieldtype not in TABLE_FIELDTYPES
            and not f.hidden
            and not f.read_only
        ]

    @staticmethod
    def _child_meta(table_field):
        child_doctype = table_field.options
        if child_doctype and frappe.db.exists("DocType", child_doctype):
            return frappe.get_meta(child_doctype)
        return None

    @staticmethod
    def _compact_permissions(meta) -> list:
        flags = ("read", "write", "create", "delete", "submit", "cancel", "amend")
        rows = []
        for p in meta.permissions:
            row = {"role": p.role, "permlevel": p.permlevel or 0}
            row.update({flag: 1 for flag in flags if p.get(flag)})
            rows.append(row)
        return rows

    @staticmethod
    def get_doctype_metadata(
        doctype: str, include_layout: bool = False, child_table: str = None, fieldnames: list = None
    ) -> Dict[str, Any]:
        """Get DocType metadata and field information.

        The default answer is compact (one line per fillable field, required fields and child
        tables first) so it survives the chat's tool-result truncation; include_layout=true
        restores the verbose shape.
        """
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' not found"}

            if not frappe.has_permission(doctype, "read"):
                return {"success": False, "error": f"No permission to access DocType '{doctype}'"}

            meta = frappe.get_meta(doctype)

            if include_layout:
                return MetadataTools._verbose_metadata(doctype, meta)

            table_fields = meta.get_table_fields()

            if child_table:
                table_field = next((t for t in table_fields if t.fieldname == child_table), None)
                if table_field is None:
                    return {
                        "success": False,
                        "error": f"'{child_table}' is not a child table of {doctype}. "
                        f"Child tables: {', '.join(t.fieldname for t in table_fields) or 'none'}",
                    }
                child_meta = MetadataTools._child_meta(table_field)
                return {
                    "success": True,
                    "doctype": doctype,
                    "child_table": {
                        "fieldname": table_field.fieldname,
                        "options": table_field.options,
                        "reqd": table_field.reqd,
                        "fields": [
                            MetadataTools._serialize_field(f) for f in MetadataTools._data_fields(child_meta)
                        ]
                        if child_meta
                        else [],
                    },
                }

            if fieldnames:
                wanted = set(fieldnames)
                details = [MetadataTools._serialize_field(f) for f in meta.fields if f.fieldname in wanted]
                for table_field in table_fields:
                    child_meta = MetadataTools._child_meta(table_field)
                    for f in child_meta.fields if child_meta else []:
                        if f.fieldname in wanted:
                            entry = MetadataTools._serialize_field(f)
                            entry["child_table"] = table_field.fieldname
                            details.append(entry)
                return {"success": True, "doctype": doctype, "field_details": details}

            data_fields = MetadataTools._data_fields(meta)
            child_tables = []
            for table_field in table_fields:
                child_meta = MetadataTools._child_meta(table_field)
                child_tables.append(
                    {
                        "fieldname": table_field.fieldname,
                        "options": table_field.options,
                        "reqd": table_field.reqd,
                        "fields": [MetadataTools._compact_field(f) for f in MetadataTools._data_fields(child_meta)]
                        if child_meta
                        else [],
                    }
                )

            return {
                "success": True,
                "doctype": doctype,
                "module": meta.module,
                "is_submittable": bool(meta.is_submittable),
                "is_tree": bool(meta.is_tree),
                "is_single": bool(meta.issingle),
                "is_child_table": bool(meta.istable),
                "naming_rule": meta.naming_rule,
                "title_field": meta.title_field,
                "format": "fields are 'fieldname: Fieldtype>options', * = required; read-only and hidden fields are omitted. "
                "Pass child_table='<fieldname>' or fieldnames=[...] for full detail, include_layout=true for everything.",
                "required_fields": [f.fieldname for f in data_fields if f.reqd],
                "child_tables": child_tables,
                "fields": [MetadataTools._compact_field(f) for f in data_fields],
                "permissions": MetadataTools._compact_permissions(meta),
            }

        except Exception as e:
            log_failure("DocType Metadata Error", e)
            return {"success": False, "error": str(e)[:2000]}

    @staticmethod
    def _verbose_metadata(doctype: str, meta) -> Dict[str, Any]:
        fields = [MetadataTools._serialize_field(field) for field in meta.fields]

        link_fields = [
            {"fieldname": field.fieldname, "label": field.label, "options": field.options}
            for field in meta.get_link_fields()
        ]

        child_tables = []
        for table_field in meta.get_table_fields():
            child_meta = MetadataTools._child_meta(table_field)
            child_tables.append(
                {
                    "fieldname": table_field.fieldname,
                    "label": table_field.label,
                    "fieldtype": table_field.fieldtype,
                    "options": table_field.options,
                    "reqd": table_field.reqd,
                    "fields": [MetadataTools._serialize_field(f) for f in child_meta.fields]
                    if child_meta
                    else [],
                }
            )

        return {
            "success": True,
            "doctype": doctype,
            "module": meta.module,
            "is_submittable": bool(meta.is_submittable),
            "is_tree": bool(meta.is_tree),
            "is_single": bool(meta.issingle),
            "is_child_table": bool(meta.istable),
            "naming_rule": meta.naming_rule,
            "title_field": meta.title_field,
            "fields": fields,
            "link_fields": link_fields,
            "child_tables": child_tables,
            "permissions": [p.as_dict() for p in meta.permissions],
        }

    @staticmethod
    def list_doctypes(module: str = None, custom_only: bool = False) -> Dict[str, Any]:
        """List all available DocTypes"""
        try:
            filters = {}
            if module:
                filters["module"] = module
            if custom_only:
                filters["custom"] = 1

            doctypes = frappe.get_all(
                "DocType",
                filters=filters,
                fields=["name", "module", "is_submittable", "is_tree", "istable", "custom", "description"],
                order_by="name",
            )

            # Filter by read permissions
            accessible_doctypes = []
            for dt in doctypes:
                if frappe.has_permission(dt.name, "read"):
                    accessible_doctypes.append(dt)

            return {
                "success": True,
                "doctypes": accessible_doctypes,
                "count": len(accessible_doctypes),
                "filters_applied": {"module": module, "custom_only": custom_only},
            }

        except Exception as e:
            log_failure("List DocTypes Error", e)
            return {"success": False, "error": str(e)[:2000]}

    @staticmethod
    def get_permissions(doctype: str, user: str = None) -> Dict[str, Any]:
        """Get permission information for a DocType"""
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' not found"}

            check_user = user or frappe.session.user

            # Reporting capabilities — not a security boundary. throw=False
            # keeps this explicit and silences the unchecked-permission rule.
            permissions = {
                "read": frappe.has_permission(doctype, "read", user=check_user, throw=False),
                "write": frappe.has_permission(doctype, "write", user=check_user, throw=False),
                "create": frappe.has_permission(doctype, "create", user=check_user, throw=False),
                "delete": frappe.has_permission(doctype, "delete", user=check_user, throw=False),
                "submit": frappe.has_permission(doctype, "submit", user=check_user, throw=False),
                "cancel": frappe.has_permission(doctype, "cancel", user=check_user, throw=False),
                "amend": frappe.has_permission(doctype, "amend", user=check_user, throw=False),
            }

            # Get user roles
            user_roles = frappe.get_roles(check_user)

            # Get DocType permission rules
            meta = frappe.get_meta(doctype)
            permission_rules = [p.as_dict() for p in meta.permissions]

            return {
                "success": True,
                "doctype": doctype,
                "user": check_user,
                "permissions": permissions,
                "user_roles": user_roles,
                "permission_rules": permission_rules,
            }

        except Exception as e:
            log_failure("Get Permissions Error", e)
            return {"success": False, "error": str(e)[:2000]}

    @staticmethod
    def get_workflow(doctype: str) -> Dict[str, Any]:
        """Get workflow information for a DocType"""
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' not found"}

            # Check if workflow exists for this DocType
            workflow = frappe.db.get_value("Workflow", {"document_type": doctype}, "name")

            if not workflow:
                return {
                    "success": True,
                    "doctype": doctype,
                    "has_workflow": False,
                    "message": f"No workflow defined for DocType '{doctype}'",
                }

            # Get workflow details
            workflow_doc = frappe.get_doc("Workflow", workflow)

            # Get workflow states
            states = []
            for state in workflow_doc.states:
                states.append(
                    {
                        "state": state.state,
                        "doc_status": state.doc_status,
                        "allow_edit": state.allow_edit,
                        "message": state.message,
                    }
                )

            # Get workflow transitions
            transitions = []
            for transition in workflow_doc.transitions:
                transitions.append(
                    {
                        "state": transition.state,
                        "action": transition.action,
                        "next_state": transition.next_state,
                        "allowed": transition.allowed,
                        "allow_self_approval": transition.allow_self_approval,
                    }
                )

            return {
                "success": True,
                "doctype": doctype,
                "has_workflow": True,
                "workflow_name": workflow_doc.name,
                "workflow_state_field": workflow_doc.workflow_state_field,
                "states": states,
                "transitions": transitions,
            }

        except Exception as e:
            log_failure("Get Workflow Error", e)
            return {"success": False, "error": str(e)[:2000]}
