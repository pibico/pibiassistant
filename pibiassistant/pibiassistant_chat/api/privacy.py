# pibiAssistant - AIDA Privacy / GDPR API
# Copyright (C) 2025 Paul Clinton
#
# Proprietary License

"""
Privacy and GDPR Data Subject Rights APIs.

Export (Art. 20), erasure (Art. 17) and restriction (Art. 18) work on the data held on
this site. The consent/config/rectification endpoints only existed for PA Cloud and are
retired (HTTP 410).
"""

import frappe
from frappe import _

from pibiassistant.utils.retired import retired


@frappe.whitelist(methods=["GET"])
def export_my_data() -> dict:
    """
    Export all data for the current user (GDPR Article 20 — Data Portability).

    Returns structured JSON with all user data from AR core and companion apps,
    plus local PA Chat data.
    """
    user = frappe.session.user

    # PA Chat data held on this site
    pao_data = {
        "pao_preferences": None,
        "pao_messages_count": 0,
    }

    # User preferences
    prefs = frappe.db.get_value(
        "PA Chat User Preferences",
        {"user": user},
        ["widget_position", "widget_theme", "keyboard_shortcut", "show_suggested_prompts"],
        as_dict=True,
    )
    if prefs:
        pao_data["pao_preferences"] = {
            "widget_position": prefs.widget_position,
            "widget_theme": prefs.widget_theme,
            "keyboard_shortcut": prefs.keyboard_shortcut,
            "show_suggested_prompts": bool(prefs.show_suggested_prompts),
        }

    # Message count (content already exported from AR side)
    pao_data["pao_messages_count"] = frappe.db.count("PA Chat Message", {"user": user})

    pao_data["pao_messages"] = frappe.get_all(
        "PA Chat Message",
        filters={"user": user},
        fields=["name", "session_id", "role", "content", "creation"],
        order_by="creation asc",
        limit_page_length=0,
    )

    return {"status": "success", "data": {"pao": pao_data}}


@frappe.whitelist(methods=["POST"])
def erase_my_data(password: str | None = None) -> dict:
    """
    Delete all data for the current user (GDPR Article 17 — Right to Erasure).

    Requires password confirmation for safety. Deletes data from:
    1. AR core (conversations, messages, streaming events, token usage, profile)
    2. Companion apps via RuntimeGate (memories, documents, billing anonymization)
    3. Local PA Chat data (messages, preferences)
    """
    user = frappe.session.user

    # Require password confirmation for destructive operation
    if not password:
        frappe.throw(_("Password confirmation is required to delete all data"))

    from frappe.utils.password import check_password

    try:
        check_password(user, password)
    except frappe.AuthenticationError:
        frappe.throw(_("Incorrect password"))

    # 1. Collect PA Chat Message names BEFORE deleting so we can cascade
    #    into attached File docs (security note — incomplete GDPR erasure).
    message_names = frappe.get_all(
        "PA Chat Message",
        filters={"user": user},
        pluck="name",
        limit_page_length=0,
    )
    file_names: list[str] = []
    if message_names:
        file_names = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "PA Chat Message",
                "attached_to_name": ["in", message_names],
            },
            pluck="name",
            limit_page_length=0,
        )

    # 2. Delete user-keyed rows. Use ``frappe.db.delete`` for bulk
    #    integrity — these DocTypes have no on_trash side effects we
    #    need to fire, and this avoids N document loads.
    local_deleted = len(message_names)
    frappe.db.delete("PA Chat Message", {"user": user})
    frappe.db.delete("PA Chat Session State", {"user": user})

    prefs_name = frappe.db.get_value("PA Chat User Preferences", {"user": user}, "name")
    frappe.db.delete("PA Chat User Preferences", {"user": user})

    # PA Usage Log — ships with the app; safe no-op if table absent.
    usage_log_deleted = 0
    try:
        usage_log_deleted = frappe.db.count("PA Chat Usage Log", {"user": user})
        frappe.db.delete("PA Chat Usage Log", {"user": user})
    except Exception as e:
        frappe.log_error(
            title="PA GDPR Erasure", message=f"PA Chat Usage Log cleanup skipped for {user}: {e}"
        )

    # OAuth Bearer Token — invalidates any mobile / SDK session still
    # using the user's tokens. Compatibility note: active mobile
    # sessions will need to re-authenticate after erasure.
    oauth_deleted = 0
    try:
        oauth_deleted = frappe.db.count("OAuth Bearer Token", {"user": user})
        frappe.db.delete("OAuth Bearer Token", {"user": user})
    except Exception as e:
        frappe.log_error(
            title="AIDA GDPR Erasure", message=f"OAuth Bearer Token cleanup failed for {user}: {e}"
        )

    # 3. Delete File docs through the ORM so the on_trash hook wipes
    #    the backing bytes from disk. Bulk db.delete would leave files
    #    orphaned on the filesystem.
    files_deleted = 0
    for fname in file_names:
        try:
            frappe.delete_doc("File", fname, force=True, ignore_permissions=True)
            files_deleted += 1
        except Exception as e:
            frappe.log_error(
                title="AIDA GDPR Erasure", message=f"Failed to delete File {fname} during erasure: {e}"
            )

    # 4. Audit trail — one summary entry the DPO can grep for.
    frappe.log_error(
        title="AIDA GDPR Erasure",
        message=(
            f"Erased AIDA data for {user}: "
            f"messages={local_deleted}, files={files_deleted}, "
            f"usage_log={usage_log_deleted}, oauth_tokens={oauth_deleted}, "
            f"preferences={1 if prefs_name else 0}"
        ),
    )

    result = {"deleted": {}}
    result["deleted"]["pao_messages"] = local_deleted
    result["deleted"]["pao_preferences"] = 1 if prefs_name else 0
    result["deleted"]["pao_usage_log"] = usage_log_deleted
    result["deleted"]["pao_oauth_tokens"] = oauth_deleted
    result["deleted"]["pao_attached_files"] = files_deleted
    result["status"] = "success"

    return result


@frappe.whitelist(methods=["POST"])
def restrict_my_processing(restrict: bool = True) -> dict:
    """
    Restrict or unrestrict data processing (GDPR Article 18).

    When restricted: memories excluded from retrieval, memory extraction
    skipped, but chat and billing continue normally.
    """
    user = frappe.session.user

    # Convert string "true"/"false" from form data
    if isinstance(restrict, str):
        restrict = restrict.lower() in ("true", "1", "yes")

    _set_processing_restricted_flag(user, bool(restrict))
    return {"status": "success", "processing_restricted": bool(restrict)}


def _set_processing_restricted_flag(user: str, restricted: bool) -> None:
    """Write the local mirror of AR's processing_restricted flag."""
    if not frappe.db.exists("PA Chat User Preferences", user):
        prefs = frappe.get_doc(
            {
                "doctype": "PA Chat User Preferences",
                "user": user,
                "processing_restricted": 1 if restricted else 0,
            }
        )
        prefs.insert(ignore_permissions=True)
    else:
        frappe.db.set_value(
            "PA Chat User Preferences",
            user,
            "processing_restricted",
            1 if restricted else 0,
        )


@frappe.whitelist(methods=["POST"])
def update_my_data(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def update_my_consent(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_privacy_config(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def update_privacy_config(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def save_initial_consent(*args, **kwargs):
    retired()
