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
Clean refactored PA API with modular handlers and proper logging
"""

from typing import Any, Dict, Optional

import frappe
from frappe import _

from pibiassistant.utils.auth import check_assistant_enabled, validate_api_credentials
from pibiassistant.utils.logger import api_logger


@frappe.whitelist(methods=["GET", "POST"])
def get_usage_statistics() -> Dict[str, Any]:
    """Get usage statistics for the assistant"""
    try:
        # SECURITY: Handle both session-based and token-based authentication
        authenticated_user = _authenticate_request()
        if not authenticated_user:
            api_logger.warning("Usage statistics requested without valid authentication")
            frappe.throw(_("Authentication required"))

        # SECURITY: Restrict global usage statistics to assistant admins
        from pibiassistant.utils.permissions import check_assistant_admin_permission

        user_roles = frappe.get_roles(authenticated_user)
        api_logger.debug(f"User {authenticated_user} has roles: {user_roles}")

        if not check_assistant_admin_permission(authenticated_user):
            api_logger.warning(
                f"Usage statistics denied for non-admin user: {authenticated_user} with roles: {user_roles}"
            )
            frappe.throw(_("Access denied - administrator permissions required"))

        api_logger.info(f"Usage statistics requested by user: {authenticated_user}")
        api_logger.info(f"Current site: {frappe.local.site}")

        from pibiassistant.utils.usage_statistics import collect_usage_statistics

        return {"success": True, "data": collect_usage_statistics()}

    except Exception as e:
        api_logger.error(f"Error getting usage statistics: {e}")
        return {"success": False, "error": str(e)}


@frappe.whitelist(methods=["GET", "POST"])
def ping() -> Dict[str, Any]:
    """Ping endpoint for testing connectivity"""
    try:
        # SECURITY: Handle both session-based and token-based authentication
        authenticated_user = _authenticate_request()
        if not authenticated_user:
            frappe.throw(_("Authentication required"))

        # SECURITY: Check if user has assistant access
        from pibiassistant.utils.permissions import check_assistant_permission

        if not check_assistant_permission(authenticated_user):
            frappe.throw(_("Access denied"))

        return {
            "success": True,
            "message": "pong",
            "timestamp": frappe.utils.now(),
            "user": authenticated_user,
        }

    except Exception as e:
        api_logger.error(f"Error in ping: {e}")
        return {"success": False, "message": _("Ping failed: {0}").format(str(e))}


def _authenticate_request() -> Optional[str]:
    """
    Handle session-based, OAuth2.0 Bearer token, and API key authentication
    Returns the authenticated user or None if authentication fails

    Note: OAuth2.0 Bearer tokens are automatically validated by Frappe's auth system
    and frappe.session.user is set before this function is called
    """

    # Check if user is already authenticated (covers session and OAuth2.0 Bearer tokens)
    if frappe.session.user and frappe.session.user != "Guest":
        # Check if user has assistant access enabled
        if not check_assistant_enabled(frappe.session.user):
            api_logger.warning(f"User {frappe.session.user} has assistant access disabled")
            return None

        auth_header = frappe.get_request_header("Authorization", "") or ""
        if auth_header.startswith("Bearer "):
            api_logger.debug(f"OAuth2.0 Bearer token authentication successful: {frappe.session.user}")
        else:
            api_logger.debug(f"Session authentication successful: {frappe.session.user}")
        return frappe.session.user

    # Fallback to API key authentication for legacy clients
    auth_header = frappe.get_request_header("Authorization") or ""
    if auth_header.startswith("token ") and ":" in auth_header[6:]:
        api_key, api_secret = auth_header[6:].split(":", 1)
        user = validate_api_credentials(api_key, api_secret)
        if user and check_assistant_enabled(user):
            # nosemgrep: frappe-setuser — user authenticated via API key:secret comparison above
            frappe.set_user(str(user))
            return str(user)
        if user:
            api_logger.warning(f"User {user} has assistant access disabled")

    api_logger.debug("Authentication failed")
    return None
