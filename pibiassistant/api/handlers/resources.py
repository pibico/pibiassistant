# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Resources handlers for MCP protocol - Skill-based implementation.
Handles resources/list and resources/read requests backed by the Skill DocType.
"""

import re
from urllib.parse import unquote
from typing import Any, Dict, List, Optional

import frappe
from frappe import _

from pibiassistant.utils.logger import api_logger
from pibiassistant.utils.permissions import increment_usage, user_can_access_shared_doc

_SKILL_URI_PREFIX = "pa://skills/"
_SKILL_ID_RE = re.compile(r"^[a-z0-9_-]+$")


class SkillManager:
    """
    Stateless helper for skill queries, filtering, and permission checks.
    Construct per call — no shared state across requests.
    """

    _LIST_FIELDS = (
        "name",
        "skill_id",
        "title",
        "description",
        "status",
        "skill_type",
        "linked_tool",
        "category",
        "owner_user",
        "visibility",
        "is_system",
        "modified",
    )

    def get_user_accessible_skills(self, user: str = None) -> List[Dict[str, Any]]:
        """
        Return all skills accessible to ``user``. A skill is accessible when:

        - the user owns it (any status), OR
        - it is Published AND one of: Public, is_system, or Shared with a role
          the user has.

        Results are deduplicated by ``skill_id``.
        """
        user = user or frappe.session.user
        user_roles = frappe.get_roles(user)

        # Single OR-filter covers own skills (any status) + published public/system.
        base = frappe.get_all(
            "PA Skill",
            filters={},
            or_filters=[
                ["owner_user", "=", user],
                ["visibility", "=", "Public"],
                ["is_system", "=", 1],
            ],
            fields=list(self._LIST_FIELDS),
        )

        # The or_filter doesn't express "status must be Published unless owner".
        # Filter that in Python (cheap — result set is already scoped).
        skills = [s for s in base if s.owner_user == user or s.status == "Published"]

        # Add Shared-with-role skills (requires a join against Has Role).
        if user_roles:
            shared = self._get_shared_skills_for_user(user, user_roles)
            seen = {s.skill_id for s in skills}
            for s in shared:
                if s.skill_id not in seen:
                    skills.append(s)
                    seen.add(s.skill_id)

        # Dedup (own skill may also be Public/system).
        deduped: List[Dict[str, Any]] = []
        seen_ids = set()
        for s in skills:
            if s.skill_id in seen_ids:
                continue
            seen_ids.add(s.skill_id)
            deduped.append(s)
        return deduped

    def _get_shared_skills_for_user(self, user: str, user_roles: List[str]) -> List[Dict]:
        """Skills shared with roles the user has (Published only)."""
        try:
            return frappe.db.sql(
                """
                SELECT DISTINCT sk.name, sk.skill_id, sk.title, sk.description,
                       sk.status, sk.skill_type, sk.linked_tool, sk.category,
                       sk.owner_user, sk.visibility, sk.is_system, sk.modified
                FROM `tabPA Skill` sk
                INNER JOIN `tabHas Role` hr
                    ON hr.parent = sk.name AND hr.parenttype = 'PA Skill'
                WHERE sk.status = 'Published'
                  AND sk.visibility = 'Shared'
                  AND hr.role IN %(roles)s
                  AND sk.owner_user != %(user)s
                """,
                {"roles": user_roles, "user": user},
                as_dict=True,
            )
        except Exception as e:
            frappe.logger("skill_manager").warning(f"Error fetching shared skills: {e}")
            return []

    def get_skill_as_resource(self, skill_info: Dict) -> Dict[str, Any]:
        """Convert a skill row to an MCP resource descriptor."""
        return {
            "uri": f"{_SKILL_URI_PREFIX}{skill_info['skill_id']}",
            "name": skill_info["title"],
            "description": skill_info["description"],
            "mimeType": "text/markdown",
        }

    def read_skill_content(self, skill_id: str) -> Optional[str]:
        """
        Return a skill's markdown content. Published skills are readable per
        the standard permission model; Drafts are readable only by the owner.

        Raises ``frappe.PermissionError`` when the caller is not permitted.
        Returns None when the skill does not exist.
        """
        skill_name = frappe.db.get_value("PA Skill", {"skill_id": skill_id}, "name")
        if not skill_name:
            return None

        skill_doc = frappe.get_doc("PA Skill", skill_name)
        user = frappe.session.user

        is_owner = skill_doc.owner_user == user
        if skill_doc.status != "Published" and not is_owner:
            frappe.throw(_("You don't have permission to access this skill"), frappe.PermissionError)

        if not user_can_access_shared_doc(skill_doc):
            frappe.throw(_("You don't have permission to access this skill"), frappe.PermissionError)

        # TODO: batch usage-counter writes if traffic grows.
        increment_usage("PA Skill", skill_name)

        return skill_doc.content

    def read_skill_file(self, skill_id: str, path: str) -> Optional[Dict[str, Any]]:
        """One bundled file of a skill (same access rules as its content). None when the skill does not exist;
        raises ValueError for an unknown file or a site without the package schema."""
        from pibiassistant.utils.skill_import import SkillImportError, read_file, schema_ready

        skill_name = frappe.db.get_value("PA Skill", {"skill_id": skill_id}, "name")
        if not skill_name:
            return None
        if not schema_ready():
            raise ValueError("Skill files are not available on this site yet")

        skill_doc = frappe.get_doc("PA Skill", skill_name)
        user = frappe.session.user
        if skill_doc.status != "Published" and skill_doc.owner_user != user:
            frappe.throw(_("You don't have permission to access this skill"), frappe.PermissionError)
        if not user_can_access_shared_doc(skill_doc):
            frappe.throw(_("You don't have permission to access this skill"), frappe.PermissionError)
        try:
            found = read_file(skill_doc, path)
        except SkillImportError as e:
            raise ValueError(str(e)) from None
        increment_usage("PA Skill", skill_name)
        return found

    @staticmethod
    def _sort_by_precedence(skills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Order skills so that competing entries for the same tool resolve the same
        way every time: app-shipped ``is_system`` skills first, then the most
        recently modified, then ``name`` as a final tie-break.

        Implemented as a stable multi-pass sort — lowest-priority key sorted first,
        highest last.
        """
        ordered = sorted(skills, key=lambda s: s.get("name") or "")
        ordered.sort(key=lambda s: str(s.get("modified") or ""), reverse=True)
        ordered.sort(key=lambda s: 0 if s.get("is_system") else 1)
        return ordered

    def get_tool_skill_map(self, user: str = None) -> Dict[str, Dict[str, str]]:
        """
        Map of ``tool_name -> {description, skill_id}`` for Published Tool-Usage
        skills accessible to ``user``. Drives token-optimization in replace mode.

        Scoped through ``get_user_accessible_skills`` so a Private (or
        Shared-to-a-role-the-user-lacks) skill can never be substituted into
        another user's tool description — see security issue #225.

        When multiple accessible skills target the same tool, precedence is
        deterministic: app-shipped ``is_system`` skills win first, then the
        most recently modified, then ``name`` as a final tie-break.
        """
        user = user or frappe.session.user
        skills = [
            s
            for s in self.get_user_accessible_skills(user)
            if s.get("status") == "Published" and s.get("skill_type") == "Tool Usage" and s.get("linked_tool")
        ]

        tool_map: Dict[str, Dict[str, str]] = {}
        for s in self._sort_by_precedence(skills):
            if s["linked_tool"] not in tool_map:
                tool_map[s["linked_tool"]] = {"description": s["description"], "skill_id": s["skill_id"]}
        return tool_map


def get_skill_manager() -> SkillManager:
    """Construct a fresh SkillManager. Kept for backwards compatibility."""
    return SkillManager()


def handle_resources_list(request_id: Optional[Any] = None) -> Dict[str, Any]:
    """Handle resources/list request - return available skill resources."""
    try:
        if not frappe.db.table_exists("PA Skill"):
            return {"resources": []}

        manager = SkillManager()
        skill_infos = manager.get_user_accessible_skills()

        resources = [manager.get_skill_as_resource(s) for s in skill_infos if s.get("status") == "Published"]

        api_logger.info(f"Resources list request completed, returned {len(resources)} resources")
        return {"resources": resources}

    except Exception as e:
        api_logger.error(f"Error in handle_resources_list: {e}")
        return {"resources": []}


SKILL_FILE_TEMPLATE = {
    "uriTemplate": f"{_SKILL_URI_PREFIX}{{skill_id}}/{{path}}",
    "name": "Skill file",
    "description": "A reference, asset or script bundled with a skill (see the files list of get_skill). Scripts are "
    "provided to read or to run on the client; this server never runs them.",
    "mimeType": "application/octet-stream",
}


def handle_resource_templates_list() -> Dict[str, Any]:
    from pibiassistant.utils.skill_import import schema_ready

    return {"resourceTemplates": [SKILL_FILE_TEMPLATE] if schema_ready() else []}


def _read_skill_file_resource(uri: str, skill_id: str, file_path: str) -> Dict[str, Any]:
    import base64

    found = SkillManager().read_skill_file(skill_id, file_path)
    if found is None:
        raise ValueError(f"Skill not found: {skill_id}")
    item: Dict[str, Any] = {"uri": uri, "mimeType": found["mime_type"]}
    if found["is_text"]:
        item["text"] = found["data"].decode("utf-8")
    else:
        item["blob"] = base64.b64encode(found["data"]).decode("ascii")
    return {"contents": [item]}


def handle_resources_read(params: Dict[str, Any], request_id: Optional[Any] = None) -> Dict[str, Any]:
    """Handle resources/read request - return skill content by URI."""
    uri = params.get("uri")

    if not isinstance(uri, str):
        raise ValueError("uri must be a string")

    if not uri.startswith(_SKILL_URI_PREFIX):
        raise ValueError(f"Unknown resource URI scheme: {uri}")

    skill_id, _sep, file_path = uri[len(_SKILL_URI_PREFIX) :].partition("/")
    if not skill_id or not _SKILL_ID_RE.match(skill_id):
        raise ValueError(f"Invalid skill_id in URI: {uri!r}")
    if _sep:
        return _read_skill_file_resource(uri, skill_id, unquote(file_path))

    try:
        manager = SkillManager()
        content = manager.read_skill_content(skill_id)
    except frappe.PermissionError:
        raise
    except Exception as e:
        api_logger.error(f"Error in handle_resources_read: {e}")
        raise

    if content is None:
        raise ValueError(f"Skill not found: {skill_id}")

    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "text/markdown",
                "text": content,
            }
        ]
    }
