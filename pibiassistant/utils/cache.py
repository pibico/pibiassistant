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
Cached PA Core Settings lookup (Frappe Redis cache) and its invalidation hook
"""

import frappe
from frappe.utils.caching import redis_cache

SERVER_SETTINGS_TTL = 1800  # 30 minutes - rarely changed


@redis_cache(ttl=SERVER_SETTINGS_TTL)
def get_cached_server_settings():
    """Cached version of server settings"""
    settings = frappe.get_single("PA Core Settings")

    # Get full server URL for MCP endpoint
    frappe_url = frappe.utils.get_url()
    mcp_endpoint_url = f"{frappe_url}/api/method/pibiassistant.api.pa_endpoint.handle_mcp"
    oauth_discovery_url = f"{frappe_url}/.well-known/openid-configuration"

    return {
        "server_enabled": settings.server_enabled,
        "mcp_endpoint_url": mcp_endpoint_url,
        "oauth_discovery_url": oauth_discovery_url,
    }


def invalidate_settings_cache(doc=None, method=None):
    """Invalidate the cached server settings (PA Core Settings on_update hook)"""
    get_cached_server_settings.clear_cache()
