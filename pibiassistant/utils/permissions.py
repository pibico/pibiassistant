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

import frappe
from frappe import get_doc

PA_ADMIN_ROLES = ("System Manager", "PA Admin")
PA_ACCESS_ROLES = PA_ADMIN_ROLES + ("PA User",)



def get_roles(user: str) -> list:
    """Retrieve roles for the specified user."""
    return [role.role for role in get_doc("User", user).roles] if user else []


# NOTE: get_permission_query_conditions function removed as Assistant Connection Log no longer exists


def get_audit_permission_query_conditions(user=None):
    """Permission query conditions for PA Audit Log."""
    if not user:
        user = frappe.session.user

    user_roles = frappe.get_roles(user)
    escaped_user = frappe.db.escape(user)

    # System Manager, PA Admin, and Auditor can see all audit logs.
    if any(role in user_roles for role in PA_ADMIN_ROLES + ("Auditor",)):
        return ""

    # PA Users can only see their own audit logs.
    if "PA User" in user_roles:
        return f"`tabPA Audit Log`.user = {escaped_user}"

    # No access for others
    return "1=0"


def check_assistant_permission(user=None):
    """Check if user has assistant access permission"""
    if not user:
        user = frappe.session.user

    user_roles = frappe.get_roles(user)

    return any(role in user_roles for role in PA_ACCESS_ROLES)


def check_assistant_admin_permission(user=None):
    """Check if user has assistant admin access permission."""
    if not user:
        user = frappe.session.user

    user_roles = frappe.get_roles(user)

    return any(role in user_roles for role in PA_ADMIN_ROLES)


def get_prompt_permission_query_conditions(user=None):
    """
    Permission query conditions for Prompt Template.

    Users can see:
    - Their own prompts (any status)
    - Published + Public prompts
    - Published + Shared prompts (if user has required role)
    - Published + System prompts
    """
    if not user:
        user = frappe.session.user

    # System Manager can see all
    if "System Manager" in frappe.get_roles(user):
        return ""

    user_roles = frappe.get_roles(user)
    escaped_user = frappe.db.escape(user)

    # Build the condition
    conditions = []

    # 1. User's own prompts
    conditions.append(f"`tabPrompt Template`.owner_user = {escaped_user}")

    # 2. Published + Public prompts
    conditions.append(
        "(`tabPrompt Template`.status = 'Published' AND `tabPrompt Template`.visibility = 'Public')"
    )

    # 3. Published + System prompts
    conditions.append("(`tabPrompt Template`.status = 'Published' AND `tabPrompt Template`.is_system = 1)")

    # 4. Published + Shared prompts with user's roles
    if user_roles:
        escaped_roles = ", ".join(frappe.db.escape(r) for r in user_roles)
        conditions.append(f"""
            (`tabPrompt Template`.status = 'Published'
             AND `tabPrompt Template`.visibility = 'Shared'
             AND EXISTS (
                SELECT 1 FROM `tabHas Role` hr
                WHERE hr.parent = `tabPrompt Template`.name
                  AND hr.parenttype = 'Prompt Template'
                  AND hr.role IN ({escaped_roles})
             ))
        """)

    return "(" + " OR ".join(conditions) + ")"


def get_skill_permission_query_conditions(user=None):
    """
    Permission query conditions for Skill.

    Users can see:
    - Their own skills (any status)
    - Published + Public skills
    - Published + Shared skills (if user has required role)
    - Published + System skills
    """
    if not user:
        user = frappe.session.user

    # System Manager can see all
    if "System Manager" in frappe.get_roles(user):
        return ""

    user_roles = frappe.get_roles(user)
    escaped_user = frappe.db.escape(user)

    conditions = []

    # 1. User's own skills
    conditions.append(f"`tabPA Skill`.owner_user = {escaped_user}")

    # 2. Published + Public skills
    conditions.append("(`tabPA Skill`.status = 'Published' AND `tabPA Skill`.visibility = 'Public')")

    # 3. Published + System skills
    conditions.append("(`tabPA Skill`.status = 'Published' AND `tabPA Skill`.is_system = 1)")

    # 4. Published + Shared skills with user's roles
    if user_roles:
        escaped_roles = ", ".join(frappe.db.escape(r) for r in user_roles)
        conditions.append(f"""
            (`tabPA Skill`.status = 'Published'
             AND `tabPA Skill`.visibility = 'Shared'
             AND EXISTS (
                SELECT 1 FROM `tabHas Role` hr
                WHERE hr.parent = `tabPA Skill`.name
                  AND hr.parenttype = 'PA Skill'
                  AND hr.role IN ({escaped_roles})
             ))
        """)

    return "(" + " OR ".join(conditions) + ")"


def user_can_access_shared_doc(doc, user: str = None) -> bool:
    """Visibility rule shared by PA Skill and Prompt Template: owner, System Manager,
    Public/Shared (to one of the user's roles) when Published, or a published system record."""
    user = user or frappe.session.user

    if doc.owner_user == user:
        return True

    roles = set(frappe.get_roles(user))
    if "System Manager" in roles:
        return True

    published = doc.status == "Published"
    if doc.visibility == "Public" and published:
        return True

    if doc.visibility == "Shared" and published and roles & {r.role for r in doc.shared_with_roles}:
        return True

    return bool(doc.is_system and published)


_USAGE_DOCTYPES = ("PA Skill", "Prompt Template")


def increment_usage(doctype: str, name: str) -> None:
    """Bump use_count/last_used for a PA Skill or Prompt Template without a full document save."""
    if doctype not in _USAGE_DOCTYPES:
        raise ValueError(f"Usage counter not supported for {doctype}")
    try:
        frappe.db.sql(
            f"UPDATE `tab{doctype}` SET use_count = use_count + 1, last_used = NOW() WHERE name = %s",
            (name,),
        )
    except Exception as e:
        frappe.logger("usage_counter").warning(f"Failed to increment usage for {doctype} {name}: {e}")
