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

from typing import Any, Dict

import frappe
from frappe import _
from frappe.model.document import Document

from pibiassistant.pibiassistant_core.server import assistantServer


class PACoreSettings(Document):
    """assistant Server Settings DocType controller"""

    def onload(self):
        """Populate computed fields when document is loaded (including first time after install)"""
        self._populate_endpoint_urls()

    def before_save(self):
        """Populate computed fields before saving"""
        self._populate_endpoint_urls()

    def _populate_endpoint_urls(self):
        """Helper to populate endpoint URLs based on current site"""
        frappe_url = frappe.utils.get_url()
        self.mcp_endpoint_url = f"{frappe_url}/api/method/pibiassistant.api.pa_endpoint.handle_mcp"
        self.oauth_discovery_url = f"{frappe_url}/.well-known/openid-configuration"

    def validate(self):
        """Validate settings before saving"""
        # Plugin validation is handled by plugin manager
        pass

    def enable_assistant_api(self):
        """Enable the assistant MCP API"""
        try:
            server = assistantServer()
            server.enable()

        except Exception as e:
            frappe.log_error(title=_("Failed to enable assistant MCP API"), message=str(e))
            raise

    def disable_assistant_api(self):
        """Disable the assistant MCP API"""
        try:
            server = assistantServer()
            server.disable()

        except Exception as e:
            frappe.log_error(title=_("Failed to disable assistant MCP API"), message=str(e))
            raise

    @frappe.whitelist()
    def get_mcp_server_info(self):
        """Get MCP server information (for backward compatibility with MCP Inspector)"""
        from pibiassistant import hooks

        frappe_url = frappe.utils.get_url()
        return {
            "mcp_endpoint": f"{frappe_url}/api/method/pibiassistant.api.pa_endpoint.handle_mcp",
            "mcp_transport": "StreamableHTTP",
            "mcp_protocol_version": "2025-03-26",
            "server_enabled": self.server_enabled,
            "server_info": {
                "name": hooks.app_name,
                "version": hooks.app_version,
                "description": hooks.app_description,
                "title": hooks.app_title,
                "publisher": hooks.app_publisher,
            },
        }

    # SSE Bridge methods removed - SSE transport is deprecated
    # Use StreamableHTTP (OAuth-based) transport instead

    @frappe.whitelist()
    def refresh_plugins(self):
        """Refresh the entire plugin system - discovery and tools"""
        try:
            from pibiassistant.core.tool_registry import get_tool_registry
            from pibiassistant.utils.plugin_manager import get_plugin_manager

            # Refresh plugin manager discovery
            plugin_manager = get_plugin_manager()
            plugin_manager.refresh_plugins()

            # Get statistics
            discovered_plugins = plugin_manager.get_discovered_plugins()
            enabled_plugins = plugin_manager.get_enabled_plugins()
            available_tools = plugin_manager.get_all_tools()

            # Include external tools from hooks
            tool_registry = get_tool_registry()
            external_tools = tool_registry._get_external_tools()
            available_tools.update(external_tools)

            frappe.msgprint(
                frappe._(
                    "Plugin system refreshed successfully.<br>Found {0} tools from {1} plugins.<br>Plugins: {2} enabled out of {3} discovered."
                ).format(
                    len(available_tools), len(enabled_plugins), len(enabled_plugins), len(discovered_plugins)
                )
            )

            return {
                "success": True,
                "stats": {
                    "total_tools": len(available_tools),
                    "discovered_plugins": len(discovered_plugins),
                    "enabled_plugins": len(enabled_plugins),
                },
            }

        except Exception as e:
            frappe.log_error(title=frappe._("Plugin Refresh Error"), message=str(e))
            frappe.throw(frappe._("Failed to refresh plugin system: {0}").format(str(e)))

    def on_update(self):
        """Handle settings update"""
        from pibiassistant.pibiassistant_core.server import get_server_instance

        server = get_server_instance()
        server_was_enabled = self.has_value_changed("server_enabled")

        # Handle MCP API enable/disable
        if self.server_enabled:
            if server_was_enabled or not server.running:
                # Enable API if it was just enabled or not running
                frappe.enqueue(
                    "pibiassistant.pibiassistant_core.server.enable_background_api",
                    queue="short",
                    enqueue_after_commit=True,
                )
        else:
            if server_was_enabled and server.running:
                # Disable API if it was just disabled
                self.disable_assistant_api()

        # Refresh tool registry if settings changed
        try:
            from pibiassistant.utils.tool_cache import refresh_tool_cache

            refresh_tool_cache()
        except Exception as e:
            frappe.log_error(title=frappe._("Tool Cache Refresh Error"), message=str(e))

    @frappe.whitelist()
    def get_plugin_status(self):
        """Get plugin status with a simplified view that links to PA Admin for full control"""
        try:
            from pibiassistant.core.tool_registry import get_tool_registry
            from pibiassistant.utils.plugin_manager import get_plugin_manager

            # Get plugin manager for plugin info
            plugin_manager = get_plugin_manager()
            tool_registry = get_tool_registry()
            discovered_plugins = plugin_manager.get_discovered_plugins()
            enabled_plugins = plugin_manager.get_enabled_plugins()
            available_tools = plugin_manager.get_all_tools()

            # Include external tools from hooks (registered via assistant_tools)
            external_tools = tool_registry._get_external_tools()
            available_tools.update(external_tools)

            # Count active tools
            active_tools = len(
                [
                    tool_name
                    for tool_name, tool_info in available_tools.items()
                    if tool_info.plugin_name in enabled_plugins
                ]
            )
            total_tools = len(available_tools)

            esc = frappe.utils.escape_html
            rows = []
            for plugin in discovered_plugins:
                plugin_name = plugin.get("name", "Unknown")
                is_enabled = plugin_name in enabled_plugins
                tools_count = len(plugin.get("tools", []))
                label = plugin.get("display_name", plugin_name.replace("_", " ").title())
                state = "on" if is_enabled else "off"
                rows.append(
                    f"""<li class="pa-ps__row pa-ps__row--{state}">
                        <span class="pa-ps__name">{esc(label)}</span>
                        <span class="pa-ps__meta">{esc(_("{0} tools").format(tools_count))}</span>
                        <span class="pa-ps__pill pa-ps__pill--{state}">{esc(_("Active") if is_enabled else _("Inactive"))}</span>
                    </li>"""
                )

            html = f"""
            <div class="pa-ps">
                <div class="pa-ps__summary">
                    <span class="pa-ps__title"><i class="ph ph-gear-six" aria-hidden="true"></i> {esc(_("Plugin System Status"))}</span>
                    <span class="pa-ps__stat"><span class="pa-ps__label">{esc(_("Active Tools"))}</span> <strong>{active_tools}</strong> / {total_tools}</span>
                    <span class="pa-ps__stat"><span class="pa-ps__label">{esc(_("Plugins"))}</span> <strong>{len(enabled_plugins)}</strong> / {len(discovered_plugins)}</span>
                    <span class="pa-ps__pill pa-ps__pill--on"><i class="ph ph-check-circle" aria-hidden="true"></i> {esc(_("Operational"))}</span>
                    <a class="btn btn-primary btn-xs pa-ps__open" href="/app/pa-admin"><i class="ph ph-arrow-square-out" aria-hidden="true"></i> {esc(_("Open PA Admin"))}</a>
                </div>
                <div class="pa-ps__panel">
                    <h6 class="pa-ps__heading"><i class="ph ph-puzzle-piece" aria-hidden="true"></i> {esc(_("Plugins"))}</h6>
                    <ul class="pa-ps__list">{"".join(rows)}</ul>
                    <p class="pa-ps__note"><i class="ph ph-info" aria-hidden="true"></i>
                        {esc(_("For individual tool management, role-based access control, and category filtering, use the PA Admin page."))}
                        <a href="/app/pa-admin">PA Admin</a></p>
                </div>
            </div>
            """

            return {"success": True, "html": html}

        except Exception as e:
            return {
                "success": False,
                "html": f"<div class='pa-ps__error' role='alert'>{frappe.utils.escape_html(_('Error loading plugin status'))}: {frappe.utils.escape_html(str(e))}</div>",
            }

    @frappe.whitelist()
    def toggle_plugin(self, plugin_name: str, action: str) -> Dict[str, Any]:
        """Enable or disable a plugin"""
        from pibiassistant.utils.plugin_manager import PluginError, get_plugin_manager

        if action not in ("enable", "disable"):
            frappe.throw(_("Invalid action: {0}").format(action))

        try:
            plugin_manager = get_plugin_manager()
            if action == "enable":
                result = plugin_manager.enable_plugin(plugin_name)
                message = _("Plugin '{0}' enabled successfully").format(plugin_name)
            else:
                result = plugin_manager.disable_plugin(plugin_name)
                message = _("Plugin '{0}' disabled successfully").format(plugin_name)
        except PluginError as e:
            frappe.throw(str(e))
        except Exception as e:
            frappe.log_error(title=frappe._("Plugin Toggle Error"), message=str(e))
            frappe.throw(frappe._("Failed to {0} plugin '{1}': {2}").format(action, plugin_name, str(e)))

        if not result:
            frappe.throw(_("Failed to {0} plugin '{1}'").format(action, plugin_name))
        frappe.msgprint(message)
        return {"success": True, "message": message}


# SSE Bridge API endpoints removed - SSE transport is deprecated
# Use StreamableHTTP (OAuth-based) transport instead


def get_context(context):
    context.title = _("assistant Server Settings")
    context.docs = _("Manage the settings for the assistant Server.")
    context.settings = frappe.get_doc("PA Core Settings")
