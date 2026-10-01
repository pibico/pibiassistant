# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Shared knowledge management — editable markdown document in the knowledge base."""

import frappe
from pibiassistant.pibiassistant_chat.api._helpers import _aida_unavailable
from frappe import _

from .auth import _ar_user_id

_LOCAL_NOTES_KEY = "aida_team_notes"


@frappe.whitelist(methods=["GET"])
def get_shared_knowledge():
    """Get shared knowledge for the current tenant."""
    try:
        from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

        client = get_pa_cloud_client()
        if not client:
            return {
                "content": frappe.db.get_default(_LOCAL_NOTES_KEY) or "",
                "embedding_status": "Pending",
                "total_chunks": 0,
                "document_id": None,
            }

        return client.get_shared_knowledge()

    except Exception as e:
        frappe.log_error(title="AIDA Team Notes", message=f"Error getting shared knowledge: {e!s}")
        return {"content": "", "embedding_status": "Pending", "total_chunks": 0}


@frappe.whitelist(methods=["POST"])
def update_shared_knowledge(content: str | None = None):
    """Update shared knowledge content. Admin only."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only administrators can edit team notes"), frappe.PermissionError)

    if content is None:
        content = ""

    try:
        from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

        client = get_pa_cloud_client()
        if not client:
            frappe.db.set_default(_LOCAL_NOTES_KEY, content)
            return {
                "content": content,
                "embedding_status": "Pending",
                "total_chunks": 0,
                "document_id": None,
            }

        return client.update_shared_knowledge(content=content)

    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(title="AIDA Team Notes", message=f"Error updating shared knowledge: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def share_memory_to_knowledge(memory_id: str | None = None):
    """Share a personal memory to the shared knowledge document. Any authenticated user."""
    if not memory_id:
        frappe.throw(_("memory_id is required"), frappe.ValidationError)

    try:
        from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

        client = get_pa_cloud_client()
        if not client:
            return _aida_unavailable()
        return client.share_memory_to_knowledge(user_id=_ar_user_id(frappe.session.user), memory_id=memory_id)

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="AIDA Team Notes", message=f"Error sharing memory to knowledge: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))
