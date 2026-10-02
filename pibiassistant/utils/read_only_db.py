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
Read-Only Database Wrapper for Security
Provides secure, read-only access to Frappe database operations
"""

import re

import frappe
from frappe import _


class ReadOnlyDatabase:
    """
    Secure read-only database wrapper that prevents dangerous SQL operations

    This proxy class wraps the original frappe.db object and only allows
    safe read-only database operations. It blocks:
    - DELETE operations
    - UPDATE operations
    - INSERT operations
    - DROP operations
    - ALTER operations
    - CREATE operations
    - TRUNCATE operations
    - Any other write operations

    Allowed operations:
    - SELECT queries
    - SHOW queries
    - DESCRIBE queries
    - EXPLAIN queries
    - Safe read methods like get_value, get_list, etc.
    """

    def __init__(self, original_db):
        """Initialize with the original database object"""
        self._original_db = original_db

        # Define safe read-only methods that are allowed
        self._allowed_methods = {
            # Core read methods
            "get_value",
            "get_values",
            "get_all",
            "get_list",
            "get_single_value",
            "get_singles_dict",
            "exists",
            "count",
            "estimate_count",
            "get_creation_count",
            # Utility methods
            "escape",
            "format_date",
            "format_datetime",
            "mogrify",
            # Schema inspection (read-only)
            "describe",
            "get_table_columns",
            "has_column",
            "has_table",
            "get_tables",
            # Connection info (read-only)
            "get_database_size",
            "get_table_size",
        }

    def sql(self, query, *args, **kwargs):
        """
        Execute SQL query with security validation

        Only allows safe read-only queries:
        - SELECT statements
        - SHOW statements
        - DESCRIBE statements
        - EXPLAIN statements

        Blocks all write operations with clear error messages.
        """
        if not query or not query.strip():
            raise frappe.ValidationError(_("Security: Empty query not allowed"))

        # Clean and normalize query for analysis
        query_upper = query.strip().upper()

        # Remove comments and normalize whitespace for better detection
        query_normalized = re.sub(r"--.*$", "", query_upper, flags=re.MULTILINE)
        query_normalized = re.sub(r"/\*.*?\*/", "", query_normalized, flags=re.DOTALL)
        query_normalized = " ".join(query_normalized.split())

        # Define dangerous keywords that indicate write operations
        dangerous_keywords = [
            "DELETE",
            "DROP",
            "INSERT",
            "UPDATE",
            "ALTER",
            "CREATE",
            "TRUNCATE",
            "REPLACE",
            "MERGE",
            "UPSERT",
            "CALL",
            "EXECUTE",
        ]

        # Check if query starts with dangerous operations
        for keyword in dangerous_keywords:
            if query_normalized.startswith(keyword + " ") or query_normalized == keyword:
                raise frappe.ValidationError(
                    _(
                        "Security: {0} operations not allowed in read-only mode. "
                        "Only SELECT, SHOW, DESCRIBE, and EXPLAIN queries are permitted."
                    ).format(keyword)
                )

        # Define allowed read-only query types
        allowed_prefixes = ["SELECT ", "SHOW ", "DESCRIBE ", "DESC ", "EXPLAIN "]

        # Check if query starts with allowed operations
        if not any(query_normalized.startswith(prefix) for prefix in allowed_prefixes):
            raise frappe.ValidationError(
                _(
                    "Security: Only SELECT, SHOW, DESCRIBE, and EXPLAIN queries are allowed in read-only mode. "
                    "Query starts with: {0}"
                ).format(query_normalized.split()[0] if query_normalized else "unknown")
            )

        # Additional security check for nested dangerous operations
        for keyword in dangerous_keywords:
            if f" {keyword} " in query_normalized or query_normalized.endswith(f" {keyword}"):
                raise frappe.ValidationError(
                    _("Security: Nested {0} operations not allowed in read-only mode").format(keyword)
                )

        try:
            # Execute the validated read-only query
            return self._original_db.sql(query, *args, **kwargs)
        except Exception as e:
            # Re-raise with additional context
            raise frappe.ValidationError(f"Database query failed: {str(e)}")

    def __getattr__(self, name):
        """
        Proxy attribute access to the original database object

        Only allows access to safe read-only methods. Blocks access to
        dangerous methods that could modify data.
        """
        # Allow access to private/internal attributes
        if name.startswith("_"):
            return getattr(self._original_db, name)

        # Check if method is in allowed list
        if name in self._allowed_methods:
            return getattr(self._original_db, name)

        # Block dangerous methods with helpful error message
        dangerous_methods = {
            "set_value",
            "set_single_value",
            "delete",
            "truncate",
            "bulk_insert",
            "bulk_update",
            "insert",
            "update_record",
        }

        if name in dangerous_methods:
            raise AttributeError(
                _(
                    "Security: Database method '{0}' is not allowed in read-only mode. "
                    "This method can modify data and is blocked for security."
                ).format(name)
            )

        # For unknown methods, be conservative and block them
        raise AttributeError(
            _(
                "Security: Database method '{0}' is not available in read-only mode. "
                "Available methods: {1}"
            ).format(name, ", ".join(sorted(self._allowed_methods)))
        )

    def __repr__(self):
        """String representation for debugging"""
        return f"<ReadOnlyDatabase wrapper for {repr(self._original_db)}>"

    def __str__(self):
        """String representation"""
        return f"ReadOnlyDatabase({str(self._original_db)})"
