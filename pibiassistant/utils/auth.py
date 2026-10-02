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

import hmac

import frappe


def validate_api_credentials(api_key, api_secret):
    """Return the enabled user matching an API key/secret pair, or None."""
    if not api_key or not api_secret:
        return None
    try:
        from frappe.utils.password import get_decrypted_password

        user = frappe.db.get_value("User", {"api_key": api_key, "enabled": 1}, "name")
        if not user:
            return None
        stored = get_decrypted_password("User", user, "api_secret", raise_exception=False)
        if stored and hmac.compare_digest(str(api_secret).encode(), str(stored).encode()):
            return user
    except Exception:
        frappe.logger().debug("API credential validation failed", exc_info=True)
    return None


def check_assistant_enabled(user: str) -> bool:
    """True when the User's assistant_enabled flag is on (default off)."""
    try:
        return bool(int(frappe.db.get_value("User", user, "assistant_enabled") or 0))
    except Exception:
        return False
