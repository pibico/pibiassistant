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
Security Configuration for pibiAssistant

This module defines role-based access control, sensitive field filtering,
and security policies following Frappe Framework standards.
"""

from typing import Any, Dict

import frappe
from frappe import _

# Sensitive fields that should be filtered based on user roles
SENSITIVE_FIELDS = {
    "all_doctypes": [
        "password",
        "new_password",
        "api_key",
        "api_secret",
        "secret_key",
        "private_key",
        "access_token",
        "refresh_token",
        "reset_password_key",
        "unsubscribe_key",
        "email_signature",
        "bank_account_no",
        "iban",
        "encryption_key",
    ],
    "User": [
        "password",
        "new_password",
        "api_key",
        "api_secret",
        "reset_password_key",
        "unsubscribe_key",
        "email_signature",
        "login_after",
        "user_type",
        "simultaneous_sessions",
        "restrict_ip",
        "last_password_reset_date",
        "last_login",
        "last_active",
        "login_before",
        "bypass_restrict_ip_check_if_2fa_enabled",
    ],
    "System Settings": [
        "password_reset_limit",
        "session_expiry",
        "session_expiry_mobile",
        "email_footer_address",
        "backup_path",
        "backup_path_db",
        "backup_path_files",
        "backup_path_private_files",
        "encryption_key",
    ],
    "Email Account": [
        "password",
        "smtp_password",
        "access_token",
        "refresh_token",
        "auth_method",
        "connected_app",
        "connected_user",
    ],
    "Integration Request": [
        "data",
        "output",
        "error",
        "headers",
    ],
    "OAuth Bearer Token": [
        "access_token",
        "refresh_token",
        "scopes",
        "expires_in",
    ],
    "Connected App": [
        "client_secret",
        "client_id",
        "redirect_uris",
    ],
    "Social Login Key": [
        "client_secret",
        "client_id",
        "base_url",
        "custom_base_url",
    ],
    "Google Settings": [
        "client_secret",
        "client_id",
    ],
    "LDAP Settings": [
        "password",
        "ldap_password",
    ],
    "Dropbox Settings": [
        "app_access_token",
        "access_token",
        "app_secret",
    ],
    "Google Drive": [
        "refresh_token",
        "access_token",
        "indexing_refresh_token",
        "indexing_access_token",
    ],
    "S3 File Attachment": [
        "access_key_id",
        "secret_access_key",
        "region_name",
        "bucket_name",
        "folder_name",
        "file_url",
        "is_private",
    ],
}

# Fields that should be hidden from PA Users but visible to admins
ADMIN_ONLY_FIELDS = {
    "all_doctypes": [
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "idx",
        "_user_tags",
        "_comments",
        "_assign",
        "_liked_by",
    ],
    "User": [
        "enabled",
        "user_type",
        "module_profile",
        "role_profile_name",
        "roles",
        "user_permissions",
        "block_modules",
        "home_settings",
        "defaults",
        "system_user",
        "allowed_in_mentions",
        "banner_image",
        "interest",
        "bio",
        "mute_sounds",
        "desk_theme",
        "simultaneous_sessions",
        "restrict_ip",
        "login_before",
        "login_after",
        "user_image",
        "logout_all_sessions",
        "reset_password_key",
        "last_password_reset_date",
        "last_login",
        "last_active",
        "login_attempts",
        "reCAPTCHA",
    ],
    "System Settings": "*",  # Hide all system settings from PA Users
    "Print Settings": "*",
    "Email Domain": "*",
    "Domain Settings": "*",
    "Energy Point Settings": "*",
    "Google Settings": "*",
    "LDAP Settings": "*",
    "OAuth Settings": "*",
    "Social Login Key": "*",
    "Dropbox Settings": "*",
}

# DocTypes whose contents are executable code, or which define the schema and the
# permission model itself. Writing to any of these over MCP is a privilege-escalation
# or code-execution surface, so it stays blocked regardless of what DocPerms say.
#
# Reads are NOT blocked here: on a stock Frappe install every one of these DocTypes
# already grants `read` to System Manager / Script Manager only, so a blocklist adds
# nothing. It only ever fires when a site admin has deliberately granted read via a
# Custom DocPerm, i.e. against explicit intent. Read access is therefore left to
# frappe.has_permission(), which validate_document_access() calls a few lines down.
# See issue #249.
WRITE_PROTECTED_DOCTYPES = [
    # Code execution
    "Server Script",
    "Client Script",
    "Custom Script",
    # Schema and customization
    "DocType",
    "DocField",
    "DocPerm",
    "Custom Field",
    "Property Setter",
    "Customize Form",
    "Customize Form Field",
    # Security and permissions
    "Role",
    "Custom Role",
    "Role Permission",
    "Custom DocPerm",
    "User Permission",
    "DocShare",
    "Module Profile",
    "Role Profile",
    # Workflow definitions (control who may transition what)
    "Workflow",
    "Workflow State",
    "Workflow Transition",
]

# Permission types treated as mutating for the purposes of WRITE_PROTECTED_DOCTYPES.
WRITE_PERM_TYPES = frozenset({"write", "create", "delete", "submit", "cancel", "amend"})

# DEPRECATED: retained only so external plugins importing this name keep working.
# The read-side blocklist is no longer enforced - see WRITE_PROTECTED_DOCTYPES above.
RESTRICTED_DOCTYPES = {"PA User": list(WRITE_PROTECTED_DOCTYPES)}




def filter_sensitive_fields(doc_dict: Dict[str, Any], doctype: str, user_role: str) -> Dict[str, Any]:
    """
    Filter out sensitive fields from document data based on user role.

    Args:
        doc_dict: Document data as dictionary
        doctype: DocType name
        user_role: User role name

    Returns:
        Filtered document dictionary
    """
    if user_role == "System Manager":
        return doc_dict  # System Manager can see all fields

    filtered_doc = doc_dict.copy()

    # Get sensitive fields for this doctype
    sensitive_fields = set()

    # Add global sensitive fields
    sensitive_fields.update(SENSITIVE_FIELDS.get("all_doctypes", []))

    # Add doctype-specific sensitive fields
    sensitive_fields.update(SENSITIVE_FIELDS.get(doctype, []))

    # Add admin-only fields for PA Users
    if user_role == "PA User":
        admin_fields = ADMIN_ONLY_FIELDS.get("all_doctypes", [])
        sensitive_fields.update(admin_fields)

        doctype_admin_fields = ADMIN_ONLY_FIELDS.get(doctype, [])
        if doctype_admin_fields == "*":
            # Hide all fields for completely restricted doctypes
            return {"error": "Access to this document type is restricted"}
        else:
            sensitive_fields.update(doctype_admin_fields)

    # Filter out sensitive fields
    for field in sensitive_fields:
        if field in filtered_doc:
            filtered_doc[field] = "***RESTRICTED***"

    return filtered_doc


def is_doctype_accessible(doctype: str, user_role: str, perm_type: str = "read") -> bool:
    """
    Check whether a role may perform ``perm_type`` on ``doctype`` at the PA layer.

    This is a coarse guard that runs *before* Frappe's own permission check, so it may
    only ever deny something Frappe would allow - never the reverse. It exists for one
    purpose: to keep MCP from writing to code-execution and schema/permission DocTypes
    even on a site whose DocPerms would permit it.

    Read access is always allowed through to frappe.has_permission(), which is the real
    control. See issue #249 for why the old read-side blocklist was removed.

    Args:
        doctype: DocType name
        user_role: User role name
        perm_type: Permission being requested (read, write, create, delete, ...)

    Returns:
        bool: True if PA allows the operation to proceed to the Frappe permission check
    """
    if user_role == "System Manager":
        return True  # System Manager is trusted at this layer

    if perm_type not in WRITE_PERM_TYPES:
        return True  # Reads and anything non-mutating defer entirely to Frappe

    return doctype not in WRITE_PROTECTED_DOCTYPES


def validate_document_access(
    user: str, doctype: str, name: str, perm_type: str = "read", data: str = ""
) -> Dict[str, Any]:
    """
    Validate if a user can access a specific document with proper Frappe permission checking.

    Args:
        user: User name
        doctype: DocType name
        name: Document name
        perm_type: Permission type (read, write, create, delete, etc.)

    Returns:
        Dictionary with validation result
    """
    try:
        if not doctype or not frappe.db.exists("DocType", doctype):
            return {"success": False, "error": _("DocType '{0}' not found").format(doctype)}

        # Get user's primary role (includes Default for non-assistant users)
        primary_role = get_user_primary_role(user)

        # PA-level guard: blocks writes to code-execution / schema DocTypes only.
        # Reads fall straight through to the Frappe permission check below.
        if not is_doctype_accessible(doctype, primary_role, perm_type):
            return {
                "success": False,
                "error": _(
                    "{0} access to {1} is blocked over MCP because it defines executable code, schema or permissions"
                ).format(perm_type.capitalize(), doctype),
            }

        # Check Frappe DocType-level permissions - this is the primary security control
        if not frappe.has_permission(doctype, perm_type, user=user):
            return {
                "success": False,
                "error": _("Insufficient {0} permissions for {1}").format(perm_type, doctype),
            }

        # Check document-level permissions (if document exists)
        if name:
            try:
                allowed = frappe.has_permission(doctype, perm_type, doc=name, user=user)
            except frappe.DoesNotExistError:
                return {"success": False, "error": _("{0} {1} not found").format(doctype, name)}
            if not allowed:
                return {
                    "success": False,
                    "error": _("Insufficient {0} permissions for {1} {2}").format(perm_type, doctype, name),
                }

            # Check if document is submitted and operation is write/delete
            if perm_type in ["write", "delete"]:
                try:
                    doc = frappe.get_doc(doctype, name)
                    if hasattr(doc, "docstatus") and doc.docstatus == 1:
                        if perm_type == "write":
                            meta = frappe.get_meta(doctype)
                            non_allowed_fields = []
                            for field in data.keys():
                                field_meta = meta.get_field(field)
                                if not field_meta or not field_meta.allow_on_submit:
                                    non_allowed_fields.append(field)
                            if non_allowed_fields:
                                return {
                                    "success": False,
                                    "error": _("Cannot modify submitted document {0} {1}").format(doctype, name),
                                }
                        elif perm_type == "delete":
                            return {
                                "success": False,
                                "error": _("Cannot delete submitted document {0} {1}").format(doctype, name),
                            }
                except Exception:
                    pass  # Document might not exist yet for create operations

        return {"success": True, "role": primary_role}

    except Exception as e:
        frappe.log_error(
            title="Error in validate_document_access",
            message=f"Error in validate_document_access: {str(e)}",
        )
        return {"success": False, "error": _("Permission validation failed")}


def get_user_primary_role(user: str) -> str:
    """
    Get the primary (highest privilege) role for a user.

    Args:
        user: User name

    Returns:
        Primary role name - specific assistant role or "Default" for all other users
    """
    user_roles = frappe.get_roles(user)

    # Check for specific assistant roles first (highest to lowest privilege)
    if "System Manager" in user_roles:
        return "System Manager"
    elif "PA Admin" in user_roles:
        return "PA Admin"
    elif "PA User" in user_roles:
        return "PA User"
    else:
        # All other users get basic tool access via Default role
        return "Default"


# DEPRECATED: audit_log_tool_access function removed
# Audit logging is now handled automatically by BaseTool._safe_execute
