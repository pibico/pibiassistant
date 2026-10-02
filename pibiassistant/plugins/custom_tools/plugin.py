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
Custom Tools Plugin for external app integration.

This plugin discovers and manages tools from external Frappe apps
using the hooks-based discovery system.
"""

from typing import Any, Dict, List

import frappe

from pibiassistant.plugins.base_plugin import BasePlugin


class CustomToolsPlugin(BasePlugin):
    """
    Plugin that aggregates tools from external Frappe apps.

    This plugin serves as a bridge between the enhanced tool registry
    and the existing plugin system, allowing external apps to contribute
    tools through the hooks mechanism.
    """

    def __init__(self):
        super().__init__()
        self._external_tools = []
        self._discovery_stats = {}

    def get_info(self) -> Dict[str, Any]:
        """Get plugin information"""
        return {
            "name": "custom_tools",
            "display_name": "Custom Tools",
            "description": "External app tool integration and management",
            "version": "1.0.0",
            "author": "pibiAssistant Team",
            "category": "Integration",
            "dependencies": [],
            "requires_restart": False,
            "external_integration": True,
        }

    def get_tools(self) -> List[str]:
        """
        Get list of tools from external apps.

        This method discovers tools from external apps using hooks.
        """
        try:
            external_tools = []

            # Safely check if frappe is initialized
            if not hasattr(frappe, "get_hooks"):
                frappe.logger("custom_tools_plugin").debug("Frappe not initialized, returning empty tools")
                return []

            # Get assistant_tools from hooks
            assistant_tools = frappe.get_hooks("assistant_tools") or []

            for tool_path in assistant_tools:
                try:
                    # Extract tool name from path (last part before class name)
                    parts = tool_path.split(".")
                    if len(parts) >= 2:
                        # Use the module name as tool identifier
                        tool_name = parts[
                            -2
                        ]  # e.g., "simple_greeting_tool" from "byot.assistant_tools.simple_greeting_tool.SimpleGreetingTool"
                        external_tools.append(tool_name)
                except Exception as e:
                    frappe.logger("custom_tools_plugin").warning(
                        f"Failed to parse tool path '{tool_path}': {e}"
                    )

            self._external_tools = external_tools
            self._update_discovery_stats()

            return external_tools

        except Exception as e:
            frappe.logger("custom_tools_plugin").error(f"Failed to discover external tools: {str(e)}")
            return []

    def _update_discovery_stats(self):
        """Update discovery statistics"""
        try:
            # Get external apps from hooks
            if hasattr(frappe, "get_hooks"):
                assistant_tools = frappe.get_hooks("assistant_tools") or []
                external_apps = set()

                for tool_path in assistant_tools:
                    try:
                        # Extract app name (first part of path)
                        app_name = tool_path.split(".")[0]
                        if app_name != "pibiassistant":
                            external_apps.add(app_name)
                    except Exception:
                        pass

                self._discovery_stats = {
                    "external_apps": list(external_apps),
                    "external_app_count": len(external_apps),
                    "external_tool_count": len(self._external_tools),
                    "total_tools_from_hooks": len(assistant_tools),
                }
            else:
                self._discovery_stats = {
                    "external_apps": [],
                    "external_app_count": 0,
                    "external_tool_count": 0,
                    "total_tools_from_hooks": 0,
                }

        except Exception as e:
            frappe.logger("custom_tools_plugin").warning(f"Failed to update discovery stats: {str(e)}")

    def get_capabilities(self) -> Dict[str, Any]:
        """Get plugin capabilities"""
        return {
            "external_discovery": {
                "hooks_based": True,
                "automatic_refresh": True,
                "multi_app_support": True,
                "dependency_validation": True,
            },
            "tool_management": {
                "dynamic_loading": True,
                "configuration_support": True,
                "audit_logging": True,
                "performance_monitoring": True,
            },
            "integration": {
                "cache_integration": True,
                "migration_hooks": True,
                "error_handling": True,
                "statistics_tracking": True,
            },
        }

    def validate_environment(self) -> tuple[bool, str]:
        """Validate plugin environment"""
        try:
            # Check if enhanced tool registry is available
            from pibiassistant.core.tool_registry import get_tool_registry

            registry = get_tool_registry()

            # Check if discovery is working
            tools = registry.get_all_tools()

            if not tools:
                return False, "No tools discovered - registry may not be functioning"

            # Check cache availability
            from pibiassistant.utils.tool_cache import get_tool_cache

            cache = get_tool_cache()
            cache_stats = cache.get_cache_stats()

            if not cache_stats.get("redis_available", False):
                return False, "Redis cache not available - performance may be degraded"

            return True, None

        except ImportError as e:
            return False, f"Enhanced tool registry not available: {str(e)}"
        except Exception as e:
            return False, f"Environment validation failed: {str(e)}"

    def on_enable(self):
        """Called when plugin is enabled"""
        try:
            frappe.logger("custom_tools_plugin").info("Custom Tools plugin enabled")

            # Trigger tool discovery to populate cache
            from pibiassistant.utils.tool_cache import refresh_tool_cache

            result = refresh_tool_cache(force=True)
            if result.get("success"):
                frappe.logger("custom_tools_plugin").info("Tool cache refreshed on plugin enable")
            else:
                frappe.logger("custom_tools_plugin").warning("Tool cache refresh failed on plugin enable")

        except Exception as e:
            frappe.logger("custom_tools_plugin").error(f"Error enabling plugin: {str(e)}")

    def on_disable(self):
        """Called when plugin is disabled"""
        try:
            frappe.logger("custom_tools_plugin").info("Custom Tools plugin disabled")

            # Clear external tool cache
            from pibiassistant.utils.tool_cache import get_tool_cache

            cache = get_tool_cache()
            cache.invalidate_cache()

            frappe.logger("custom_tools_plugin").info("Tool cache cleared on plugin disable")

        except Exception as e:
            frappe.logger("custom_tools_plugin").error(f"Error disabling plugin: {str(e)}")
