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
Visualization Constants and Schema Definitions

Central definitions for chart types, templates, color schemes,
and configuration schemas used throughout the visualization plugin.
"""

# Chart type definitions with capabilities
CHART_TYPES = {
    "basic": {
        "bar": {
            "name": "Bar Chart",
            "description": "Compare values across categories",
            "required_fields": ["x_field", "y_field"],
            "supports_grouping": True,
            "supports_time_series": True,
            "best_for": ["comparisons", "rankings", "categorical_data"],
            "max_categories": 50,
        },
        "line": {
            "name": "Line Chart",
            "description": "Show trends and changes over time",
            "required_fields": ["x_field", "y_field"],
            "supports_grouping": True,
            "supports_time_series": True,
            "best_for": ["trends", "time_series", "continuous_data"],
            "max_data_points": 1000,
        },
        "pie": {
            "name": "Pie Chart",
            "description": "Show proportions and percentages",
            "required_fields": ["x_field"],
            "supports_grouping": False,
            "supports_time_series": False,
            "best_for": ["proportions", "parts_of_whole", "categorical_breakdown"],
            "max_categories": 10,
        },
        "scatter": {
            "name": "Scatter Plot",
            "description": "Explore relationships between variables",
            "required_fields": ["x_field", "y_field"],
            "supports_grouping": True,
            "supports_time_series": False,
            "best_for": ["correlations", "relationships", "outlier_detection"],
            "max_data_points": 5000,
        },
    },
    "statistical": {
        "histogram": {
            "name": "Histogram",
            "description": "Show distribution of numeric data",
            "required_fields": ["y_field"],
            "supports_grouping": False,
            "supports_time_series": False,
            "best_for": ["distributions", "frequency_analysis", "data_exploration"],
            "max_data_points": 10000,
        },
        "box": {
            "name": "Box Plot",
            "description": "Show statistical summary and outliers",
            "required_fields": ["y_field"],
            "supports_grouping": True,
            "supports_time_series": False,
            "best_for": ["statistics", "outliers", "group_comparisons"],
            "max_groups": 20,
        },
        "heatmap": {
            "name": "Heatmap",
            "description": "Visualize patterns in matrix data",
            "required_fields": ["x_field", "y_field", "value_field"],
            "supports_grouping": False,
            "supports_time_series": False,
            "best_for": ["correlations", "patterns", "matrix_data"],
            "max_cells": 10000,
        },
    },
    "performance": {
        "gauge": {
            "name": "Gauge Chart",
            "description": "Show progress towards targets",
            "required_fields": ["y_field", "target_value"],
            "supports_grouping": False,
            "supports_time_series": False,
            "best_for": ["kpis", "targets", "performance_tracking"],
            "max_gauges": 1,
        },
        "funnel": {
            "name": "Funnel Chart",
            "description": "Show process conversion rates",
            "required_fields": ["stages"],
            "supports_grouping": False,
            "supports_time_series": False,
            "best_for": ["conversions", "processes", "sales_funnels"],
            "max_stages": 10,
        },
        "waterfall": {
            "name": "Waterfall Chart",
            "description": "Show step-by-step changes",
            "required_fields": ["categories", "values"],
            "supports_grouping": False,
            "supports_time_series": False,
            "best_for": ["cash_flow", "variance_analysis", "step_changes"],
            "max_steps": 20,
        },
    },
    "advanced": {
        "treemap": {
            "name": "Treemap",
            "description": "Show hierarchical data as nested rectangles",
            "required_fields": ["hierarchy_field", "size_field"],
            "supports_grouping": True,
            "supports_time_series": False,
            "best_for": ["hierarchies", "portfolios", "market_share"],
            "max_levels": 4,
        },
        "sunburst": {
            "name": "Sunburst Chart",
            "description": "Show hierarchical data in circular layout",
            "required_fields": ["hierarchy_field", "size_field"],
            "supports_grouping": True,
            "supports_time_series": False,
            "best_for": ["hierarchies", "drill_down", "multi_level_data"],
            "max_levels": 5,
        },
        "radar": {
            "name": "Radar Chart",
            "description": "Compare multiple metrics across dimensions",
            "required_fields": ["metrics"],
            "supports_grouping": True,
            "supports_time_series": False,
            "best_for": ["multi_dimensional", "comparisons", "performance_profiles"],
            "max_metrics": 12,
        },
    },
}

# KPI card configurations
KPI_CARD_TYPES = {
    "basic": {
        "name": "Basic KPI",
        "description": "Simple metric display",
        "features": ["current_value", "label"],
        "supports_comparison": False,
    },
    "comparison": {
        "name": "Comparison KPI",
        "description": "KPI with trend comparison",
        "features": ["current_value", "previous_value", "percentage_change", "trend_indicator"],
        "supports_comparison": True,
    },
    "target": {
        "name": "Target KPI",
        "description": "KPI with target achievement",
        "features": ["current_value", "target_value", "achievement_percentage", "progress_bar"],
        "supports_comparison": True,
    },
    "sparkline": {
        "name": "Sparkline KPI",
        "description": "KPI with mini trend chart",
        "features": ["current_value", "mini_chart", "trend_indicator"],
        "supports_comparison": True,
    },
}

# Dashboard template categories
TEMPLATE_CATEGORIES = {
    "sales": {
        "name": "Sales Analytics",
        "description": "Revenue, customer, and sales performance tracking",
        "primary_doctypes": ["Sales Invoice", "Sales Order", "Customer", "Lead", "Opportunity"],
        "key_metrics": ["revenue", "orders", "customers", "conversion_rate"],
        "typical_charts": ["line", "bar", "pie", "funnel", "gauge"],
        "default_time_span": "current_quarter",
    },
    "financial": {
        "name": "Financial Performance",
        "description": "P&L, cash flow, and financial health monitoring",
        "primary_doctypes": ["GL Entry", "Journal Entry", "Payment Entry"],
        "key_metrics": ["profit", "cash_flow", "expenses", "ratios"],
        "typical_charts": ["line", "waterfall", "gauge", "bar"],
        "default_time_span": "current_year",
    },
    "inventory": {
        "name": "Inventory Management",
        "description": "Stock levels, movement, and warehouse analytics",
        "primary_doctypes": ["Stock Ledger Entry", "Item", "Warehouse"],
        "key_metrics": ["stock_levels", "turnover", "movements", "valuation"],
        "typical_charts": ["bar", "heatmap", "scatter", "gauge"],
        "default_time_span": "current_month",
    },
    "hr": {
        "name": "Human Resources",
        "description": "Employee metrics, attendance, and performance",
        "primary_doctypes": ["Employee", "Attendance", "Leave Application"],
        "key_metrics": ["headcount", "attendance", "performance", "turnover"],
        "typical_charts": ["pie", "bar", "line", "heatmap"],
        "default_time_span": "current_quarter",
    },
    "executive": {
        "name": "Executive Summary",
        "description": "High-level KPIs and strategic metrics",
        "primary_doctypes": ["Company", "Sales Invoice", "GL Entry"],
        "key_metrics": ["revenue", "profit", "growth", "efficiency"],
        "typical_charts": ["gauge", "line", "kpi_card", "funnel"],
        "default_time_span": "current_year",
    },
}

# Color schemes and palettes
COLOR_SCHEMES = {
    "professional": {
        "primary": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
        "description": "Professional business colors",
        "best_for": ["executive", "financial"],
    },
    "vibrant": {
        "primary": ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"],
        "description": "Bright, energetic colors",
        "best_for": ["sales", "marketing"],
    },
    "pastel": {
        "primary": ["#a8dadc", "#457b9d", "#1d3557", "#f1faee", "#e63946"],
        "description": "Soft, easy on eyes",
        "best_for": ["hr", "general"],
    },
    "monochrome": {
        "primary": ["#2c3e50", "#34495e", "#7f8c8d", "#95a5a6", "#bdc3c7"],
        "description": "Grayscale professional",
        "best_for": ["formal", "print"],
    },
    "category20": {
        "primary": [
            "#1f77b4",
            "#aec7e8",
            "#ff7f0e",
            "#ffbb78",
            "#2ca02c",
            "#98df8a",
            "#d62728",
            "#ff9896",
            "#9467bd",
            "#c5b0d5",
        ],
        "description": "Extended color palette",
        "best_for": ["detailed_breakdowns"],
    },
}

# Aggregation methods with descriptions
AGGREGATION_METHODS = {
    "sum": {
        "name": "Sum",
        "description": "Add all values together",
        "applicable_to": ["numeric"],
        "use_cases": ["revenue", "quantities", "totals"],
    },
    "count": {
        "name": "Count",
        "description": "Count number of records",
        "applicable_to": ["all"],
        "use_cases": ["orders", "customers", "transactions"],
    },
    "avg": {
        "name": "Average",
        "description": "Calculate mean value",
        "applicable_to": ["numeric"],
        "use_cases": ["prices", "ratings", "performance"],
    },
    "min": {
        "name": "Minimum",
        "description": "Find lowest value",
        "applicable_to": ["numeric", "date"],
        "use_cases": ["lowest_price", "earliest_date"],
    },
    "max": {
        "name": "Maximum",
        "description": "Find highest value",
        "applicable_to": ["numeric", "date"],
        "use_cases": ["highest_sale", "latest_date"],
    },
    "distinct": {
        "name": "Distinct Count",
        "description": "Count unique values",
        "applicable_to": ["all"],
        "use_cases": ["unique_customers", "product_varieties"],
    },
}

# Time span definitions
TIME_SPANS = {
    "current_week": {
        "name": "Current Week",
        "description": "Monday to Sunday of current week",
        "sql_condition": "WEEK(field) = WEEK(CURDATE()) AND YEAR(field) = YEAR(CURDATE())",
    },
    "current_month": {
        "name": "Current Month",
        "description": "First to last day of current month",
        "sql_condition": "MONTH(field) = MONTH(CURDATE()) AND YEAR(field) = YEAR(CURDATE())",
    },
    "current_quarter": {
        "name": "Current Quarter",
        "description": "Current business quarter",
        "sql_condition": "QUARTER(field) = QUARTER(CURDATE()) AND YEAR(field) = YEAR(CURDATE())",
    },
    "current_year": {
        "name": "Current Year",
        "description": "January to December of current year",
        "sql_condition": "YEAR(field) = YEAR(CURDATE())",
    },
    "last_week": {
        "name": "Last Week",
        "description": "Previous complete week",
        "sql_condition": "WEEK(field) = WEEK(CURDATE()) - 1 AND YEAR(field) = YEAR(CURDATE())",
    },
    "last_month": {
        "name": "Last Month",
        "description": "Previous complete month",
        "sql_condition": "MONTH(field) = MONTH(CURDATE()) - 1 AND YEAR(field) = YEAR(CURDATE())",
    },
    "last_quarter": {
        "name": "Last Quarter",
        "description": "Previous complete quarter",
        "sql_condition": "QUARTER(field) = QUARTER(CURDATE()) - 1 AND YEAR(field) = YEAR(CURDATE())",
    },
    "last_year": {
        "name": "Last Year",
        "description": "Previous complete year",
        "sql_condition": "YEAR(field) = YEAR(CURDATE()) - 1",
    },
    "last_6_months": {
        "name": "Last 6 Months",
        "description": "Rolling 6 month period",
        "sql_condition": "field >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)",
    },
    "last_12_months": {
        "name": "Last 12 Months",
        "description": "Rolling 12 month period",
        "sql_condition": "field >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)",
    },
}

# Export formats and capabilities
EXPORT_FORMATS = {
    "pdf": {
        "name": "PDF Document",
        "description": "Professional document format",
        "supports_multiple_charts": True,
        "supports_interactive": False,
        "best_for": ["reports", "presentations", "printing"],
    },
    "png": {
        "name": "PNG Image",
        "description": "High-quality image format",
        "supports_multiple_charts": False,
        "supports_interactive": False,
        "best_for": ["embedding", "sharing", "documentation"],
    },
    "excel": {
        "name": "Excel Spreadsheet",
        "description": "Data and charts in Excel format",
        "supports_multiple_charts": True,
        "supports_interactive": True,
        "best_for": ["data_analysis", "further_processing"],
    },
    "powerpoint": {
        "name": "PowerPoint Presentation",
        "description": "Presentation-ready slides",
        "supports_multiple_charts": True,
        "supports_interactive": False,
        "best_for": ["presentations", "meetings", "reports"],
    },
    "html": {
        "name": "HTML Page",
        "description": "Interactive web format",
        "supports_multiple_charts": True,
        "supports_interactive": True,
        "best_for": ["web_sharing", "interactive_exploration"],
    },
}

# Widget interaction types
WIDGET_INTERACTIONS = {
    "click_to_filter": {
        "name": "Click to Filter",
        "description": "Click chart element to filter other charts",
        "triggers": ["click"],
        "affects": ["filters", "data"],
    },
    "hover_highlight": {
        "name": "Hover Highlight",
        "description": "Highlight related elements on hover",
        "triggers": ["hover"],
        "affects": ["visual_highlight"],
    },
    "drill_down": {
        "name": "Drill Down",
        "description": "Navigate to detailed view",
        "triggers": ["double_click"],
        "affects": ["navigation", "data_scope"],
    },
    "brush_select": {
        "name": "Brush Selection",
        "description": "Select range to zoom or filter",
        "triggers": ["drag"],
        "affects": ["zoom", "filters"],
    },
}

# Dashboard layout grid system
LAYOUT_GRID = {
    "columns": 12,
    "row_height": 60,  # pixels
    "margin": [10, 10],  # [x, y] margins
    "container_padding": [10, 10],  # [x, y] padding
    "breakpoints": {"lg": 1200, "md": 996, "sm": 768, "xs": 480, "xxs": 0},
    "cols": {"lg": 12, "md": 10, "sm": 6, "xs": 4, "xxs": 2},
}

# Validation schemas
DASHBOARD_SCHEMA = {
    "type": "object",
    "required": ["name", "charts"],
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 100},
        "description": {"type": "string", "maxLength": 500},
        "charts": {"type": "array", "minItems": 1, "maxItems": 50},
        "filters": {"type": "object"},
        "layout": {"type": "object"},
        "settings": {"type": "object"},
    },
}

CHART_SCHEMA = {
    "type": "object",
    "required": ["chart_type", "title"],
    "properties": {
        "chart_type": {
            "type": "string",
            "enum": list(CHART_TYPES["basic"].keys())
            + list(CHART_TYPES["statistical"].keys())
            + list(CHART_TYPES["performance"].keys())
            + list(CHART_TYPES["advanced"].keys()),
        },
        "title": {"type": "string", "minLength": 1, "maxLength": 100},
        "x_field": {"type": "string"},
        "y_field": {"type": "string"},
        "filters": {"type": "object"},
        "styling": {"type": "object"},
    },
}

# Error messages
ERROR_MESSAGES = {
    "invalid_chart_type": "Chart type '{chart_type}' is not supported",
    "missing_required_field": "Required field '{field}' is missing for {chart_type} chart",
    "invalid_doctype": "DocType '{doctype}' does not exist or is not accessible",
    "insufficient_data": "Insufficient data available for visualization (minimum {min_records} records required)",
    "invalid_field": "Field '{field}' does not exist in {doctype}",
    "aggregation_not_supported": "Aggregation '{aggregation}' is not supported for field type '{field_type}'",
    "template_not_found": "Dashboard template '{template}' is not available",
    "permission_denied": "Insufficient permissions to access {resource}",
    "export_failed": "Export to {format} failed: {reason}",
    "sharing_failed": "Failed to share dashboard: {reason}",
}

# Success messages
SUCCESS_MESSAGES = {
    "dashboard_created": "Dashboard '{name}' created successfully with {chart_count} charts",
    "chart_created": "Chart '{title}' created successfully",
    "template_applied": "Template '{template}' applied successfully",
    "dashboard_shared": "Dashboard shared with {recipient_count} recipients",
    "export_completed": "Dashboard exported to {format} successfully",
    "migration_completed": "Migration from old visualization system completed successfully",
}

# Performance limits
PERFORMANCE_LIMITS = {
    "max_dashboard_charts": 50,
    "max_data_points_per_chart": 10000,
    "max_categories_pie_chart": 10,
    "max_series_line_chart": 10,
    "max_dashboard_filters": 20,
    "max_drill_down_levels": 5,
    "cache_duration_minutes": 30,
    "export_timeout_seconds": 300,
}
