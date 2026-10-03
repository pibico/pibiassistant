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
Get Skill Tool for the Core Plugin.
Read-only access to PA Skill playbooks, filtered by the caller's permissions.
"""

from typing import Any, Dict

import frappe
from frappe import _

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.limits import clamp_int, clamp_limit
from pibiassistant.plugins.query_errors import permission_error_result

ADMIN_ROLES = {"System Manager", "PA Admin"}
CONTENT_MAX_CHARS = 15000
USAGE_NOTE = (
    "This server does not run scripts or fill templates. Scripts and templates are listed in files and can be read "
    "with get_skill_file, to read or to run on the client. When you must produce the deliverable here, write it as "
    "Markdown (headings, tables, lists) following the skill's structure so it can be converted to docx or PDF afterwards."
)


class GetSkill(BaseTool):
    """Look up PA Skills: list the ones the user can use, or read one in full."""

    def __init__(self):
        super().__init__()
        self.name = "get_skill"
        self.description = (
            "Read a PA Skill, a step-by-step playbook for a kind of task. Call without skill_id to list "
            "the available skills (skill_id, title, description), then call with a skill_id to read its "
            "instructions and follow them. A skill imported from a package also lists its files (references, assets, scripts): "
            "read them with get_skill_file. Only published skills you may use are returned."
        )
        self.requires_permission = None

        self.inputSchema = {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string", "description": "Skill id from the list; omit to list skills."},
                "query": {"type": "string", "description": "Optional text to narrow the list by title or description."},
                "offset": {"type": "integer", "default": 0, "description": "With skill_id: character offset to continue reading a skill whose result has truncated=true (use its next_offset)."},
                "limit": {"type": "integer", "default": 50, "maximum": 100, "description": "Maximum skills listed."},
            },
        }

    @staticmethod
    def _add_package_info(skill: Dict[str, Any]) -> None:
        """Version and bundled files of an imported skill package (nothing on a site without the schema)."""
        from pibiassistant.utils.skill_import import file_rows, schema_ready

        if not schema_ready():
            return
        name = frappe.db.get_value("PA Skill", {"skill_id": skill["skill_id"]}, ["name", "version"], as_dict=True)
        if not name:
            return
        files = file_rows(frappe.get_doc("PA Skill", name.name))
        if name.version:
            skill["version"] = name.version
        if files:
            skill["files"] = files
            skill["usage_note"] = USAGE_NOTE

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not frappe.has_permission("PA Skill", "read"):
            return {"success": False, "error": "Insufficient read permissions for PA Skill"}

        is_admin = bool(ADMIN_ROLES & set(frappe.get_roles()))
        filters: Dict[str, Any] = {} if is_admin else {"status": "Published"}
        skill_id = (arguments.get("skill_id") or "").strip()

        try:
            if skill_id:
                rows = frappe.get_list(
                    "PA Skill",
                    filters={**filters, "skill_id": skill_id},
                    fields=["skill_id", "title", "status", "skill_type", "description", "linked_tool", "content"],
                    limit=1,
                )
                if not rows:
                    return {"success": False, "error": f"Skill '{skill_id}' not found", "error_type": "not_found"}
                skill = dict(rows[0])
                self._add_package_info(skill)
                content = skill.get("content") or ""
                offset = clamp_int(arguments.get("offset"), 0, 0, len(content))
                end = offset + CONTENT_MAX_CHARS
                skill["truncated"] = len(content) > end
                skill["content"] = content[offset:end]
                if skill["truncated"]:
                    skill["next_offset"] = end
                    skill["note"] = _("Content truncated. Call get_skill again with offset={0} to continue, or read pa://skills/{1} for the whole text.").format(end, skill["skill_id"])
                return {"success": True, "skill": skill}

            query = (arguments.get("query") or "").strip()
            or_filters = (
                [["title", "like", f"%{query}%"], ["description", "like", f"%{query}%"]] if query else None
            )
            rows = frappe.get_list(
                "PA Skill",
                filters=filters,
                or_filters=or_filters,
                fields=["skill_id", "title", "status", "skill_type", "description"],
                order_by="title asc",
                limit=clamp_limit(arguments.get("limit"), 50, 100),
            )
            return {"success": True, "skills": [dict(r) for r in rows], "count": len(rows)}
        except frappe.PermissionError as e:
            return permission_error_result(e, _("Insufficient read permissions for PA Skill"))
        except Exception as e:
            return {"success": False, "error": str(e) or type(e).__name__}


get_skill = GetSkill
