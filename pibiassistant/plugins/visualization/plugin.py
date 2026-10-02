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
Visualization Plugin - Main plugin registration

The main plugin class that registers all visualization tools and manages
the comprehensive dashboard system for Business Intelligence.
"""

from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _

from pibiassistant.plugins.base_plugin import BasePlugin


class VisualizationPlugin(BasePlugin):
    """
    Comprehensive Visualization Plugin for Business Intelligence.

    Transforms pibiAssistant from basic chart generation to a complete
    Business Intelligence suite with dashboard-focused approach.
    """

    def get_info(self) -> Dict[str, Any]:
        """Get plugin information"""
        return {
            "name": "visualization",
            "display_name": "Visualization & Business Intelligence",
            "description": "Create Frappe dashboards and dashboard charts",
            "version": "1.0.0",
            "author": "pibiAssistant Team",
            "category": "Business Intelligence",
            "dependencies": ["pandas", "numpy", "matplotlib", "seaborn", "plotly"],
            "requires_restart": False,
        }

    def get_tools(self) -> List[str]:
        """Get list of tools provided by this plugin"""
        return [
            # Core dashboard management
            "create_dashboard",
            "create_dashboard_chart",
            "list_user_dashboards",
        ]

    def validate_environment(self) -> Tuple[bool, Optional[str]]:
        """Validate that required dependencies are available"""
        info = self.get_info()
        dependencies = info["dependencies"]

        # Check Python dependencies
        can_enable, error = self._check_dependencies(dependencies)
        if not can_enable:
            return can_enable, error

        # Check Frappe environment
        try:
            # Test basic imports and functionality
            import matplotlib.pyplot as plt
            import numpy as np
            import pandas as pd

            # Test Frappe dashboard capabilities
            dashboard_exists = frappe.db.exists("DocType", "Dashboard")
            if not dashboard_exists:
                return False, _("Dashboard DocType not found. Ensure Frappe is properly installed.")

            # Test data access
            test_df = pd.DataFrame({"test": [1, 2, 3]})
            result = test_df.sum()

            self.logger.info("Visualization plugin validation passed")
            return True, None

        except Exception as e:
            return False, _("Environment validation failed: {0}").format(str(e))

    def get_capabilities(self) -> Dict[str, Any]:
        """Get plugin capabilities"""
        return {
            "dashboard_creation": {"frappe_dashboard": True, "user_sharing": True, "role_sharing": True},
            "chart_types": ["line", "bar", "percentage", "pie", "donut", "heatmap"],
            "aggregations": ["Count", "Sum", "Average"],
        }

    def on_enable(self) -> None:
        """Called when plugin is enabled"""
        super().on_enable()

        try:
            # Initialize visualization environment
            self._setup_visualization_environment()

            # Log successful enable
            self.logger.info("Visualization plugin enabled successfully")

        except Exception as e:
            self.logger.error(f"Failed to enable visualization plugin: {str(e)}")
            raise e

    def on_disable(self) -> None:
        """Called when plugin is disabled"""
        super().on_disable()

        try:
            # Cleanup visualization resources
            self._cleanup_visualization_environment()

            # Note: Don't delete user dashboards, just disable plugin features
            self.logger.info("Visualization plugin disabled")

        except Exception as e:
            self.logger.warning(f"Cleanup failed during disable: {str(e)}")

    def _setup_visualization_environment(self):
        """Setup visualization environment"""
        try:
            # Configure matplotlib for server environment
            import matplotlib

            matplotlib.use("Agg")  # Use non-interactive backend
            import matplotlib.pyplot as plt

            plt.ioff()  # Turn off interactive mode

            # Check for Insights app integration
            self._check_insights_integration()

            self.logger.debug("Visualization environment configured")

        except Exception as e:
            self.logger.warning(f"Failed to configure visualization environment: {str(e)}")

    def _check_insights_integration(self):
        """Check if Insights app is available for integration"""
        try:
            insights_available = "insights" in frappe.get_installed_apps()
            if insights_available:
                self.logger.info("Insights app detected - enabling advanced dashboard features")
            else:
                self.logger.info("Insights app not found - using Frappe Dashboard fallback")

        except Exception as e:
            self.logger.warning(f"Failed to check Insights integration: {str(e)}")

    def _cleanup_visualization_environment(self):
        """Cleanup visualization resources"""
        try:
            import matplotlib.pyplot as plt

            plt.close("all")  # Close all figures
            self.logger.debug("Visualization cleanup completed")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup visualization: {str(e)}")
