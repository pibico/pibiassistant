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
Base class for all plugins in pibiAssistant.
Provides interface for plugin discovery, validation, and lifecycle management.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _


class BasePlugin(ABC):
    """
    Base class for all plugins.

    Plugins extend the functionality of pibiAssistant by providing:
    - Additional tools
    - Custom capabilities
    - Optional features that can be enabled/disabled

    Each plugin must implement the abstract methods to provide:
    - Plugin information (name, version, description)
    - Tool list
    - Environment validation
    - Lifecycle hooks
    """

    def __init__(self):
        self.logger = frappe.logger(self.__class__.__module__)

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Get plugin information.

        Returns:
            Dict containing plugin metadata:
            {
                'name': str,              # Unique plugin identifier
                'display_name': str,      # Human-readable name
                'description': str,       # Plugin description
                'version': str,           # Plugin version
                'author': str,            # Plugin author
                'dependencies': List[str], # Required Python packages
                'requires_restart': bool  # Whether enabling requires restart
            }
        """
        pass

    @abstractmethod
    def get_tools(self) -> List[str]:
        """
        Get list of tool class names provided by this plugin.

        Returns:
            List of tool class names that should be loaded from
            the plugin's tools directory.
        """
        pass

    @abstractmethod
    def validate_environment(self) -> Tuple[bool, Optional[str]]:
        """
        Validate that the environment meets plugin requirements.

        Checks for:
        - Required Python packages
        - System dependencies
        - Configuration requirements
        - Permission requirements

        Returns:
            Tuple of (can_enable, error_message)
            - can_enable: True if plugin can be enabled
            - error_message: Error details if can_enable is False
        """
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get plugin capabilities for MCP protocol.

        Returns:
            Dict of capabilities this plugin adds to the server
        """
        return {"experimental": {self.get_info()["name"]: True}}

    def on_enable(self) -> None:
        """
        Hook called when plugin is enabled.

        Override to perform initialization:
        - Setup database tables
        - Initialize services
        - Register hooks
        """
        info = self.get_info()
        self.logger.info(_("Plugin {0} enabled successfully").format(info["name"]))

    def on_disable(self) -> None:
        """
        Hook called when plugin is disabled.

        Override to perform cleanup:
        - Close connections
        - Cleanup resources
        - Unregister hooks
        """
        info = self.get_info()
        self.logger.info(_("Plugin {0} disabled successfully").format(info["name"]))

    def _check_dependencies(self, dependencies: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Helper method to check if dependencies are installed.

        Args:
            dependencies: List of package names to check

        Returns:
            Tuple of (all_installed, missing_packages)
        """
        missing = []

        for dep in dependencies:
            try:
                __import__(dep)
            except ImportError:
                missing.append(dep)

        if missing:
            return False, _("Missing dependencies: {0}").format(", ".join(missing))

        return True, None
