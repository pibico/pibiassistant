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
Remove deprecated DocTypes that are replaced by enhanced tool registry.

This patch removes:
- Assistant Plugin Repository
- Assistant Plugin Config
- Assistant Tool Registry

These are replaced by the new dynamic discovery system with Redis caching.
"""

import frappe
from frappe import _


def execute():
    """Execute the migration to remove deprecated DocTypes"""

    frappe.logger("migration").info("Starting removal of deprecated plugin DocTypes")

    # DocTypes to remove
    deprecated_doctypes = [
        "Assistant Plugin Repository",
        "Assistant Plugin Config",
        "Assistant Tool Registry",
    ]

    for doctype_name in deprecated_doctypes:
        try:
            # Check if DocType exists
            if frappe.db.exists("DocType", doctype_name):
                # First, delete all documents of this type
                delete_doctype_data(doctype_name)

                # Then delete the DocType itself
                frappe.delete_doc("DocType", doctype_name, ignore_missing=True, force=True)

                frappe.logger("migration").info(f"Removed DocType: {doctype_name}")
            else:
                frappe.logger("migration").debug(f"DocType {doctype_name} not found, skipping")

        except Exception as e:
            frappe.logger("migration").error(f"Failed to remove {doctype_name}: {str(e)}")
            # Continue with other DocTypes even if one fails
            continue

    # Clear any related caches
    try:
        frappe.clear_cache()
        frappe.logger("migration").info("Cleared caches after DocType removal")
    except Exception as e:
        frappe.logger("migration").warning(f"Failed to clear cache: {str(e)}")

    # Trigger tool cache refresh with new system
    try:
        from pibiassistant.utils.tool_cache import refresh_tool_cache

        result = refresh_tool_cache(force=True)
        if result.get("success"):
            frappe.logger("migration").info("Successfully refreshed tool cache with new system")
        else:
            frappe.logger("migration").warning(f"Tool cache refresh had issues: {result}")
    except Exception as e:
        frappe.logger("migration").warning(f"Could not refresh tool cache: {str(e)}")

    frappe.logger("migration").info("Completed removal of deprecated plugin DocTypes")


def delete_doctype_data(doctype_name):
    """
    Delete all documents of a specific DocType.

    Args:
        doctype_name: Name of the DocType to clean up
    """
    try:
        # Get all documents of this type
        documents = frappe.get_all(doctype_name, pluck="name")

        if documents:
            frappe.logger("migration").info(f"Deleting {len(documents)} documents of type {doctype_name}")

            # Delete documents in batches to avoid memory issues
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]

                for doc_name in batch:
                    try:
                        frappe.delete_doc(doctype_name, doc_name, ignore_missing=True, force=True)
                    except Exception as e:
                        frappe.logger("migration").warning(
                            f"Failed to delete {doctype_name} {doc_name}: {str(e)}"
                        )

                # Commit batch to avoid transaction timeout
                frappe.db.commit()

        else:
            frappe.logger("migration").debug(f"No documents found for {doctype_name}")

    except Exception as e:
        frappe.logger("migration").error(f"Failed to delete data for {doctype_name}: {str(e)}")
        # Don't raise exception - let the migration continue
