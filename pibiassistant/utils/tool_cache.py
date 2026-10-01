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
Simplified tool cache utilities.
The new plugin manager handles most state management, so this is now mainly for backward compatibility.
"""

from typing import Any, Dict

import frappe


def refresh_tool_cache(force: bool = False) -> Dict[str, Any]:
    """
    Refresh tool cache by refreshing the plugin manager.

    Args:
        force: Force refresh regardless of cache age

    Returns:
        Refresh status and statistics
    """
    try:
        from pibiassistant.utils.plugin_manager import get_plugin_manager

        plugin_manager = get_plugin_manager()
        result = plugin_manager.refresh_plugins()

        if result:
            available_tools = plugin_manager.get_all_tools()
            enabled_plugins = plugin_manager.get_enabled_plugins()

            return {
                "success": True,
                "refreshed": True,
                "reason": "Plugin manager refreshed",
                "stats": {"enabled_plugins": len(enabled_plugins), "available_tools": len(available_tools)},
            }
        else:
            return {"success": False, "refreshed": False, "reason": "Plugin manager refresh failed"}

    except Exception as e:
        frappe.logger("tool_cache").error(f"Failed to refresh tool cache: {e}")
        return {"success": False, "error": str(e)}


# Legacy compatibility functions
def get_tool_cache():
    """Legacy compatibility - returns a dummy cache object"""
    return DummyCache()


class DummyCache:
    """Dummy cache object for backward compatibility"""

    def get_cache_stats(self):
        """Return basic cache stats"""
        return {"redis_available": True, "cache_enabled": True, "cached_tools_count": 0}

    def invalidate_cache(self, tool_name=None):
        """Legacy compatibility - delegate to plugin manager refresh"""
        return refresh_tool_cache(force=True)


# Export functions for external use
__all__ = ["refresh_tool_cache", "get_tool_cache"]
