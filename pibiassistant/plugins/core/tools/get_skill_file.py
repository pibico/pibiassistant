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
Get Skill File Tool for the Core Plugin.
Read one file bundled with an imported skill package (references/, assets/, scripts/).
"""

import base64
from typing import Any, Dict

import frappe
from frappe import _

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.limits import clamp_int
from pibiassistant.plugins.query_errors import permission_error_result

TEXT_CHUNK = 15000
BINARY_CHUNK = 300_000  # bytes per call; a base64 chunk is a third larger


class GetSkillFile(BaseTool):
    """Read a bundled skill file in chunks, with the same access rules as the skill itself."""

    def __init__(self):
        super().__init__()
        self.name = "get_skill_file"
        self.description = (
            "Read one file bundled with a skill: a reference document, a template or asset, or a script. Use the "
            "files list that get_skill returns for the skill. Text comes back in chunks (call again with next_offset); "
            "binaries (docx, images...) come back as base64 chunks. Scripts are only read, never executed by this "
            "server."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string", "description": "Skill id."},
                "path": {"type": "string", "description": "File path from the skill's files list, e.g. references/guide.md"},
                "offset": {"type": "integer", "default": 0, "description": "Character (text) or byte (binary) offset to continue from."},
            },
            "required": ["skill_id", "path"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        skill_id = (arguments.get("skill_id") or "").strip()
        path = (arguments.get("path") or "").strip()
        if not skill_id or not path:
            return {"success": False, "error": "skill_id and path are required"}
        if not frappe.has_permission("PA Skill", "read"):
            return {"success": False, "error": "Insufficient read permissions for PA Skill"}
        try:
            from pibiassistant.api.handlers.resources import SkillManager

            found = SkillManager().read_skill_file(skill_id, path)
        except frappe.PermissionError as e:
            return permission_error_result(e, _("Insufficient read permissions for PA Skill"))
        except ValueError as e:
            return {"success": False, "error": str(e), "error_type": "not_found"}
        except Exception as e:
            return {"success": False, "error": str(e) or type(e).__name__}
        if found is None:
            return {"success": False, "error": f"Skill '{skill_id}' not found", "error_type": "not_found"}

        data = found["data"]
        result: Dict[str, Any] = {"success": True, "skill_id": skill_id, "path": found["path"], "kind": found["kind"], "mime_type": found["mime_type"], "size": found["size"]}
        if found["is_text"]:
            text = data.decode("utf-8")
            offset = clamp_int(arguments.get("offset"), 0, 0, len(text))
            end = offset + TEXT_CHUNK
            result.update({"encoding": "text", "content": text[offset:end], "truncated": len(text) > end})
            if result["truncated"]:
                result["next_offset"] = end
        else:
            offset = clamp_int(arguments.get("offset"), 0, 0, len(data))
            end = offset + BINARY_CHUNK
            result.update({"encoding": "base64", "content": base64.b64encode(data[offset:end]).decode("ascii"), "truncated": len(data) > end})
            if result["truncated"]:
                result["next_offset"] = end
        return result


get_skill_file = GetSkillFile
