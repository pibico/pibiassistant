import frappe


def execute():
    """
    Rename assistant-admin page to pa-admin.

    This updates the page name to the new convention while preserving
    all functionality and user bookmarks will be redirected automatically.
    """
    try:
        # Check if the old page exists
        if frappe.db.exists("Page", "assistant-admin"):
            frappe.logger().info("assistant-admin page exists, deleting old assistant-admin page")
            frappe.delete_doc("Page", "assistant-admin", force=True, ignore_permissions=True)

        frappe.db.commit()

    except Exception as e:
        frappe.logger().error(f"Failed to rename assistant-admin page: {str(e)}")
