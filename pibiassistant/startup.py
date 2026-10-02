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
Clean startup initialization using the new plugin manager.
Removes workarounds and provides proper initialization flow.
"""

import frappe

from pibiassistant.utils.logger import api_logger


def startup():
    """App startup initialization"""
    try:
        # Persist encryption_key before any Password-field write (e.g. the AIDA API keys in
        # PA Core Settings). A missing/racy key corrupts the first stored secret and surfaces
        # as "Encryption key is invalid" on connect.
        from frappe.utils.password import get_encryption_key

        get_encryption_key()

        # Initialize plugin manager - this automatically loads enabled plugins from settings
        initialize_plugin_system()

        # Initialize assistant server if enabled
        settings = frappe.get_single("PA Core Settings")
        if settings and settings.server_enabled:
            from pibiassistant.pibiassistant_core.server import start_server

            start_server()

    except Exception as e:
        api_logger.debug(f"Startup error (non-critical): {e}")


def initialize_plugin_system():
    """Initialize the plugin system with clean architecture"""
    try:
        from pibiassistant.utils.plugin_manager import get_plugin_manager

        # Get plugin manager - this automatically initializes and loads enabled plugins
        plugin_manager = get_plugin_manager()

        # Get stats for logging
        enabled_plugins = plugin_manager.get_enabled_plugins()
        available_tools = plugin_manager.get_all_tools()

        api_logger.info(
            f"Plugin system initialized: {len(enabled_plugins)} plugins enabled, "
            f"{len(available_tools)} tools available"
        )

    except Exception as e:
        api_logger.error(f"Failed to initialize plugin system: {e}")
