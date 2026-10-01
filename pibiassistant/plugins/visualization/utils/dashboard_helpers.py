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
Dashboard Helper Utilities

Common utility functions for dashboard operations including
layout management, data validation, and performance optimization.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _

from ..constants.viz_definitions import (
    CHART_TYPES,
    ERROR_MESSAGES,
    PERFORMANCE_LIMITS,
    TEMPLATE_CATEGORIES,
    TIME_SPANS,
)


def validate_dashboard_config(config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate dashboard configuration"""
    try:
        # Check required fields
        if not config.get("name"):
            return False, "Dashboard name is required"

        if not config.get("charts"):
            return False, "At least one chart is required"

        # Check chart count limit
        if len(config["charts"]) > PERFORMANCE_LIMITS["max_dashboard_charts"]:
            return False, f"Maximum {PERFORMANCE_LIMITS['max_dashboard_charts']} charts allowed per dashboard"

        # Validate each chart
        for i, chart in enumerate(config["charts"]):
            is_valid, error = validate_chart_config(chart)
            if not is_valid:
                return False, f"Chart {i + 1}: {error}"

        return True, None

    except Exception as e:
        return False, f"Validation error: {str(e)}"


def validate_chart_config(chart: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate individual chart configuration"""
    try:
        chart_type = chart.get("chart_type")

        # Check if chart type is supported
        if not is_chart_type_supported(chart_type):
            return False, ERROR_MESSAGES["invalid_chart_type"].format(chart_type=chart_type)

        # Get chart type definition
        chart_def = get_chart_type_definition(chart_type)
        if not chart_def:
            return False, f"Chart type definition not found for {chart_type}"

        # Check required fields
        for required_field in chart_def.get("required_fields", []):
            if not chart.get(required_field):
                return False, ERROR_MESSAGES["missing_required_field"].format(
                    field=required_field, chart_type=chart_type
                )

        return True, None

    except Exception as e:
        return False, f"Chart validation error: {str(e)}"


def is_chart_type_supported(chart_type: str) -> bool:
    """Check if chart type is supported"""
    for category in CHART_TYPES.values():
        if chart_type in category:
            return True
    return False


def get_chart_type_definition(chart_type: str) -> Optional[Dict[str, Any]]:
    """Get chart type definition"""
    for category in CHART_TYPES.values():
        if chart_type in category:
            return category[chart_type]
    return None


def optimize_chart_for_data_size(chart_config: Dict[str, Any], data_count: int) -> Dict[str, Any]:
    """Optimize chart configuration based on data size"""
    try:
        optimized_config = chart_config.copy()
        chart_type = chart_config.get("chart_type")

        # Get chart limits
        chart_def = get_chart_type_definition(chart_type)
        if not chart_def:
            return optimized_config

        # Apply data size optimizations
        if chart_type == "pie" and data_count > chart_def.get("max_categories", 10):
            # Group small categories into "Others"
            optimized_config["group_small_categories"] = True
            optimized_config["max_categories"] = chart_def["max_categories"]

        elif chart_type in ["bar", "line"] and data_count > 100:
            # Enable data sampling or aggregation
            optimized_config["data_sampling"] = True
            optimized_config["sample_size"] = min(data_count, 1000)

        elif chart_type == "scatter" and data_count > 5000:
            # Enable point reduction for performance
            optimized_config["point_reduction"] = True
            optimized_config["max_points"] = 5000

        return optimized_config

    except Exception as e:
        frappe.logger("dashboard_helpers").error(f"Chart optimization failed: {str(e)}")
        return chart_config


def generate_dashboard_layout(charts: List[Dict], layout_type: str = "auto") -> Dict[str, Any]:
    """Generate optimal dashboard layout"""
    try:
        layout = {"type": layout_type, "grid": {"columns": 12, "row_height": 60}, "charts": []}

        if layout_type == "auto":
            # Auto-arrange charts based on type and priority
            layout["charts"] = _auto_arrange_charts(charts)
        elif layout_type == "grid":
            # Simple grid layout
            layout["charts"] = _grid_arrange_charts(charts)
        elif layout_type == "priority":
            # Priority-based layout with important charts larger
            layout["charts"] = _priority_arrange_charts(charts)

        return layout

    except Exception as e:
        frappe.logger("dashboard_helpers").error(f"Layout generation failed: {str(e)}")
        return {"type": "simple", "charts": []}


def _auto_arrange_charts(charts: List[Dict]) -> List[Dict]:
    """Automatically arrange charts based on type and content"""
    arranged_charts = []
    row = 0
    col = 0

    # Sort charts by priority and type
    sorted_charts = sorted(charts, key=lambda x: (x.get("priority", "medium"), x.get("chart_type", "bar")))

    for chart in sorted_charts:
        chart_type = chart.get("chart_type", "bar")

        # Determine chart size based on type
        if chart_type in ["gauge", "kpi_card"]:
            width, height = 3, 3  # Small widgets
        elif chart_type in ["pie"]:
            width, height = 4, 4  # Medium square
        elif chart_type in ["line", "bar"]:
            width, height = 8, 5  # Wide charts
        elif chart_type in ["table"]:
            width, height = 12, 6  # Full width
        else:
            width, height = 6, 4  # Default size

        # Check if chart fits in current row
        if col + width > 12:
            row += height + 1
            col = 0

        arranged_charts.append({**chart, "layout": {"x": col, "y": row, "w": width, "h": height}})

        col += width

    return arranged_charts


def _grid_arrange_charts(charts: List[Dict]) -> List[Dict]:
    """Arrange charts in simple grid layout"""
    arranged_charts = []
    charts_per_row = 2
    chart_width = 6
    chart_height = 4

    for i, chart in enumerate(charts):
        row = (i // charts_per_row) * (chart_height + 1)
        col = (i % charts_per_row) * chart_width

        arranged_charts.append({**chart, "layout": {"x": col, "y": row, "w": chart_width, "h": chart_height}})

    return arranged_charts


def _priority_arrange_charts(charts: List[Dict]) -> List[Dict]:
    """Arrange charts with priority-based sizing"""
    arranged_charts = []
    row = 0

    # Group by priority
    high_priority = [c for c in charts if c.get("priority") == "high"]
    medium_priority = [c for c in charts if c.get("priority") == "medium"]
    low_priority = [c for c in charts if c.get("priority") == "low"]

    # Place high priority charts first (larger)
    for chart in high_priority:
        arranged_charts.append({**chart, "layout": {"x": 0, "y": row, "w": 12, "h": 6}})
        row += 7

    # Place medium priority charts (medium size)
    col = 0
    for chart in medium_priority:
        if col + 6 > 12:
            row += 5
            col = 0

        arranged_charts.append({**chart, "layout": {"x": col, "y": row, "w": 6, "h": 4}})
        col += 6

    # Place low priority charts (smaller)
    if col > 0:
        row += 5
    col = 0
    for chart in low_priority:
        if col + 4 > 12:
            row += 4
            col = 0

        arranged_charts.append({**chart, "layout": {"x": col, "y": row, "w": 4, "h": 3}})
        col += 4

    return arranged_charts


def validate_data_access(doctype: str, user: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Validate user access to data source"""
    try:
        user = user or frappe.session.user

        # Check if doctype exists
        if not frappe.db.exists("DocType", doctype):
            return False, ERROR_MESSAGES["invalid_doctype"].format(doctype=doctype)

        # Check read permission
        if not frappe.has_permission(doctype, "read", user=user):
            return False, ERROR_MESSAGES["permission_denied"].format(resource=doctype)

        return True, None

    except Exception as e:
        return False, f"Access validation error: {str(e)}"


def get_field_info(doctype: str, field: str) -> Optional[Dict[str, Any]]:
    """Get field information and metadata"""
    try:
        meta = frappe.get_meta(doctype)

        for df in meta.fields:
            if df.fieldname == field:
                return {
                    "fieldname": df.fieldname,
                    "fieldtype": df.fieldtype,
                    "label": df.label,
                    "options": df.options,
                    "mandatory": df.reqd,
                    "unique": df.unique,
                    "is_numeric": df.fieldtype in ["Int", "Float", "Currency", "Percent"],
                    "is_date": df.fieldtype in ["Date", "Datetime"],
                    "is_categorical": df.fieldtype in ["Select", "Link", "Data"],
                }

        return None

    except Exception:
        return None


def suggest_chart_type(x_field_info: Dict, y_field_info: Dict, data_count: int) -> str:
    """Suggest optimal chart type based on field types and data"""
    try:
        # Time series data
        if x_field_info.get("is_date") and y_field_info.get("is_numeric"):
            return "line"

        # Categorical vs numeric
        if x_field_info.get("is_categorical") and y_field_info.get("is_numeric"):
            if data_count <= 10:
                return "pie"
            else:
                return "bar"

        # Numeric vs numeric
        if x_field_info.get("is_numeric") and y_field_info.get("is_numeric"):
            return "scatter"

        # Default to bar chart
        return "bar"

    except Exception:
        return "bar"


def calculate_dashboard_performance_score(config: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate dashboard performance score and recommendations"""
    try:
        score = 100
        recommendations = []

        # Check number of charts
        chart_count = len(config.get("charts", []))
        if chart_count > 20:
            score -= 20
            recommendations.append("Consider reducing number of charts for better performance")
        elif chart_count > 10:
            score -= 10
            recommendations.append("Monitor dashboard loading time with this many charts")

        # Check for heavy chart types
        heavy_charts = [c for c in config.get("charts", []) if c.get("chart_type") in ["heatmap", "scatter"]]
        if len(heavy_charts) > 3:
            score -= 15
            recommendations.append("Limit complex chart types (heatmap, scatter) for better performance")

        # Check for real-time features
        if config.get("auto_refresh"):
            if config.get("refresh_interval") in ["1_minute", "5_minutes"]:
                score -= 10
                recommendations.append("Frequent auto-refresh may impact performance")

        return {
            "score": max(0, score),
            "rating": "excellent"
            if score >= 90
            else "good"
            if score >= 70
            else "fair"
            if score >= 50
            else "poor",
            "recommendations": recommendations,
        }

    except Exception as e:
        return {
            "score": 0,
            "rating": "unknown",
            "recommendations": [f"Performance calculation failed: {str(e)}"],
        }


def get_template_compatibility(doctype: str) -> List[str]:
    """Get compatible dashboard templates for a doctype"""
    try:
        compatible_templates = []

        for template_key, template_info in TEMPLATE_CATEGORIES.items():
            if doctype in template_info["primary_doctypes"]:
                compatible_templates.append(template_key)

        # Add general compatibility
        if not compatible_templates:
            compatible_templates.append("custom")

        return compatible_templates

    except Exception:
        return ["custom"]


def sanitize_dashboard_name(name: str) -> str:
    """Sanitize dashboard name for safe usage"""
    try:
        import re

        # Remove special characters, keep alphanumeric and spaces
        sanitized = re.sub(r"[^a-zA-Z0-9\s\-_]", "", name)

        # Limit length
        sanitized = sanitized[:100]

        # Ensure not empty
        if not sanitized.strip():
            sanitized = "Untitled Dashboard"

        return sanitized.strip()

    except Exception:
        return "Untitled Dashboard"


def generate_chart_title(chart_config: Dict[str, Any]) -> str:
    """Generate descriptive chart title if not provided"""
    try:
        if chart_config.get("title"):
            return chart_config["title"]

        chart_type = chart_config.get("chart_type", "chart")
        x_field = chart_config.get("x_field", "")
        y_field = chart_config.get("y_field", "")
        aggregate = chart_config.get("aggregate", "")

        # Generate based on available information
        if x_field and y_field:
            if aggregate and aggregate != "count":
                return f"{aggregate.title()} {y_field} by {x_field}"
            else:
                return f"{y_field} by {x_field}"
        elif y_field:
            return f"{y_field} {chart_type.title()}"
        elif x_field:
            return f"{x_field} Distribution"
        else:
            return f"{chart_type.title()} Chart"

    except Exception:
        return "Chart"


# Export utility functions
__all__ = [
    "validate_dashboard_config",
    "validate_chart_config",
    "is_chart_type_supported",
    "get_chart_type_definition",
    "optimize_chart_for_data_size",
    "generate_dashboard_layout",
    "validate_data_access",
    "get_field_info",
    "suggest_chart_type",
    "calculate_dashboard_performance_score",
    "get_template_compatibility",
    "sanitize_dashboard_name",
    "generate_chart_title",
]
