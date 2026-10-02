# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0-or-later — see <https://www.gnu.org/licenses/>.

import frappe
from frappe import _


@frappe.whitelist()
def get_tool_registry() -> dict:
    """Fetch assistant Tool Registry with detailed information."""
    frappe.only_for(["System Manager", "PA Admin"])
    from pibiassistant.utils.plugin_manager import get_plugin_manager

    try:
        plugin_manager = get_plugin_manager()
        tools = plugin_manager.get_all_tools()
        enabled_plugins = plugin_manager.get_enabled_plugins()

        formatted_tools = []
        for tool_name, tool_info in tools.items():
            formatted_tools.append(
                {
                    "name": tool_name.replace("_", " ").title(),
                    "category": tool_info.plugin_name.replace("_", " ").title(),
                    "category_id": tool_info.plugin_name,
                    "description": tool_info.description,
                    "enabled": tool_info.plugin_name in enabled_plugins,
                }
            )

        formatted_tools.sort(key=lambda x: (x["category"], x["name"]))

        return {"tools": formatted_tools}
    except Exception as e:
        frappe.log_error(
            title="Failed to get tool registry",
            message=f"Failed to get tool registry: {str(e)}",
        )
        return {"tools": []}


@frappe.whitelist()
def get_plugin_stats() -> dict:
    """Get plugin statistics for admin dashboard."""
    frappe.only_for(["System Manager", "PA Admin"])
    from pibiassistant.utils.plugin_manager import get_plugin_manager

    try:
        plugin_manager = get_plugin_manager()
        discovered = plugin_manager.get_discovered_plugins()
        enabled = plugin_manager.get_enabled_plugins()

        plugins = []
        for plugin in discovered:
            plugins.append(
                {
                    "name": plugin["display_name"],
                    "plugin_id": plugin["name"],
                    "enabled": plugin["name"] in enabled,
                }
            )

        return {"enabled_count": len(enabled), "total_count": len(discovered), "plugins": plugins}
    except Exception as e:
        frappe.log_error(title="Failed to get plugin stats", message=f"Failed to get plugin stats: {str(e)}")
        return {"enabled_count": 0, "total_count": 0, "plugins": []}


@frappe.whitelist()
def get_tool_stats() -> dict:
    """Get tool statistics for admin dashboard."""
    frappe.only_for(["System Manager", "PA Admin"])
    from pibiassistant.core.tool_registry import get_tool_registry
    from pibiassistant.utils.plugin_manager import get_plugin_manager

    try:
        plugin_manager = get_plugin_manager()
        tool_registry = get_tool_registry()

        tools = plugin_manager.get_all_tools()

        external_tools = tool_registry._get_external_tools()
        tools.update(external_tools)

        categories = {}
        for _tool_name, tool_info in tools.items():
            category = tool_info.plugin_name
            categories[category] = categories.get(category, 0) + 1

        return {"total_tools": len(tools), "categories": categories}
    except Exception as e:
        frappe.log_error(title="Failed to get tool stats", message=f"Failed to get tool stats: {str(e)}")
        return {"total_tools": 0, "categories": {}}


@frappe.whitelist(methods=["POST"])
def toggle_plugin(plugin_name: str, enable: bool):
    """Enable or disable a plugin.

    Uses atomic DocType updates via PA Plugin Configuration for
    reliable state persistence across Gunicorn workers.
    """
    frappe.only_for(["System Manager", "PA Admin"])
    from pibiassistant.utils.plugin_manager import PluginNotFoundError, get_plugin_manager

    try:
        plugin_manager = get_plugin_manager()

        if enable:
            plugin_manager.enable_plugin(plugin_name)
            message = _("Plugin '{0}' enabled successfully").format(plugin_name)
        else:
            plugin_manager.disable_plugin(plugin_name)
            message = _("Plugin '{0}' disabled successfully").format(plugin_name)

        cache = frappe.cache()
        cache.delete_keys("plugin_*")
        cache.delete_keys("tool_registry_*")
        cache.delete_keys("pa_plugin_*")

        frappe.clear_document_cache("PA Plugin Configuration", plugin_name)
        frappe.clear_document_cache("PA Core Settings", "PA Core Settings")

        plugin_manager.refresh_plugins()

        return {"success": True, "message": message}
    except PluginNotFoundError as e:
        return {"success": False, "message": _("Error: {0}").format(str(e))}
    except Exception as e:
        frappe.log_error(
            title="Failed to toggle plugin",
            message=f"Failed to toggle plugin '{plugin_name}': {str(e)}",
        )
        return {"success": False, "message": _("Error: {0}").format(str(e))}
