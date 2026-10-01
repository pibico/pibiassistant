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
from frappe import _


def get_user_roles(user):
    """Fetch the roles assigned to a user."""
    return frappe.get_roles(user)


def has_permission(doctype, permission_type, user=None):
    """Check if the user has the specified permission for the given DocType."""
    if user is None:
        user = frappe.session.user
    return frappe.has_permission(doctype, permission_type, user=user)


def validate_api_key(api_key):
    """Validate the provided API key."""
    if not api_key or not frappe.db.exists("API Key", api_key):
        raise frappe.PermissionError(_("Invalid API Key"))


def validate_api_secret(api_secret):
    """Validate the provided API secret."""
    if not api_secret or not frappe.db.exists("API Secret", api_secret):
        raise frappe.PermissionError(_("Invalid API Secret"))


def check_authentication(api_key, api_secret):
    """Check if the provided API key and secret are valid."""
    validate_api_key(api_key)
    validate_api_secret(api_secret)


def is_authenticated(user):
    """Check if the user is authenticated."""
    return user != "Guest" and frappe.session.user != "Guest"


def validate_api_credentials(api_key, api_secret):
    """
    Validate API credentials and return the authenticated user
    Returns user name if valid, None if invalid
    """
    try:
        # Custom validation using database lookup and password verification
        user_data = frappe.db.get_value("User", {"api_key": api_key, "enabled": 1}, ["name", "api_secret"])

        if user_data:
            user, stored_secret = user_data
            # Compare the provided secret with stored secret
            from frappe.utils.password import get_decrypted_password

            decrypted_secret = get_decrypted_password("User", user, "api_secret")

            if api_secret == decrypted_secret:
                return user

        return None
    except Exception:
        return None
