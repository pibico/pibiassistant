# pibiAssistant - Chat Sessions API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Session lifecycle endpoints — list, history, archive, continue."""

import frappe
from frappe import _

from pibiassistant.pibiassistant_chat.doctype.pa_chat_session_state.pa_chat_session_state import (
    PAChatSessionState,
)

from .._helpers import _safe_error, _validate_session_id
from .._untrusted import wrap_untrusted


def _int_param(value, default: int, low: int, high: int | None = None) -> int:
    """Parse a numeric request parameter; non-numeric is a client error, out-of-range is clamped."""
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        frappe.throw(_("Invalid pagination parameter"), frappe.ValidationError)
    number = max(low, number)
    return min(number, high) if high is not None else number


@frappe.whitelist(methods=["GET"])
def get_session_history(session_id: str, limit: int = 30, offset: int = 0) -> dict:
    """
    Get messages for a session with pagination.

    Reads from the local PA Chat Message rows, which are authoritative under
    the stateless default (and a stateful app still mirrors every turn locally).
    Returns most recent messages (ordered chronologically), with has_more flag
    for pagination.

    Args:
            session_id: Conversation session ID
            limit: Max messages to return (default 30, max 100)
            offset: Number of messages to skip from the end (for loading older messages)

    Returns:
            dict: { "messages": [...], "has_more": bool }
    """
    from pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message import (
        PAChatMessage,
    )

    _validate_session_id(session_id)
    limit = _int_param(limit, 30, 1, 100)
    offset = _int_param(offset, 0, 0)

    # Ownership check — prevent cross-user session read (IDOR).
    # A user may only read a session that contains at least one of their own messages.
    user = frappe.session.user
    has_local = frappe.db.exists("PA Chat Message", {"session_id": session_id})
    if has_local and not frappe.db.exists("PA Chat Message", {"session_id": session_id, "user": user}):
        frappe.throw(_("Session not found"), frappe.PermissionError)

    # Local read is authoritative — includes tool_calls and attachments.
    # Pass user to scope the query even for edge cases (e.g. shared assistant rows).
    local_messages = PAChatMessage.get_session_messages(session_id, limit=limit, offset=offset, user=user)
    if local_messages is not None:
        return local_messages

    return {"messages": [], "has_more": False}


@frappe.whitelist(methods=["GET"])
def get_user_sessions(limit: int = 20) -> list:
    """
    Get user's recent chat sessions for history sidebar.

    Returns sessions grouped with preview (first message) and timestamps.

    Args:
            limit: Maximum number of sessions to return (default 20)

    Returns:
            list: Sessions with session_id, preview, started, last_activity
    """
    limit = _int_param(limit, 20, 1, 100)
    try:
        return _sessions_with_previews(frappe.session.user, 0, limit, _("New conversation"))
    except Exception as e:
        frappe.log_error(title="AIDA Sessions Error", message=f"Error getting user sessions: {e!s}")
        return []


def _sessions_with_previews(user: str, archived: int, limit: int, empty_preview: str) -> list:
    from frappe.query_builder.functions import Substring
    from pypika.functions import Count, Max, Min

    FM = frappe.qb.DocType("PA Chat Message")
    sessions = (
        frappe.qb.from_(FM)
        .select(
            FM.session_id,
            Min(FM.creation).as_("started"),
            Max(FM.creation).as_("last_activity"),
            Count(FM.name).as_("message_count"),
        )
        .where(FM.user == user)
        .where(FM.is_archived == archived)
        .groupby(FM.session_id)
        .orderby("last_activity", order=frappe.qb.desc)
        .limit(limit)
        .run(as_dict=True)
    )
    if not sessions:
        return []

    # First user message per session; only its first 101 chars leave the DB.
    first = (
        frappe.qb.from_(FM)
        .select(FM.session_id, Min(FM.creation).as_("first_creation"))
        .where(FM.user == user)
        .where(FM.role == "user")
        .where(FM.session_id.isin([s["session_id"] for s in sessions]))
        .groupby(FM.session_id)
        .as_("f")
    )
    rows = (
        frappe.qb.from_(FM)
        .join(first)
        .on((FM.session_id == first.session_id) & (FM.creation == first.first_creation))
        .select(FM.session_id, Substring(FM.content, 1, 101).as_("content"))
        .where(FM.user == user)
        .where(FM.role == "user")
        .run(as_dict=True)
    )
    preview_map: dict[str, str] = {}
    for row in rows:
        if row.session_id not in preview_map:
            content = row.content or ""
            preview_map[row.session_id] = content[:100] + ("..." if len(content) > 100 else "")
    for session in sessions:
        session["preview"] = preview_map.get(session["session_id"], empty_preview)
    return sessions


@frappe.whitelist(methods=["POST"])
def create_session() -> dict:
    """
    Create a new chat session for the current user.

    Returns:
            dict: Session information with session_id
    """
    import uuid

    try:
        session_id = str(uuid.uuid4())
        return {
            "success": True,
            "session_id": session_id,
            "user": frappe.session.user,
            "created": frappe.utils.now(),
        }
    except Exception as e:
        frappe.log_error(title="AIDA Session Create Error", message=f"Error creating session: {e!s}")
        return {"success": False, "error": _safe_error(e, "AIDA Session Create Error")}


@frappe.whitelist(methods=["POST"])
def archive_session(session_id: str) -> dict:
    """
    Archive a conversation locally and drop its zero-retention state blob.

    The local PA Chat Messages are preserved (marked is_archived=1) so the
    user retains their data on their own instance. Under the stateless default
    AR holds no conversation to delete, so cleanup is purely local: archive the
    rows and drop the session-state blob.

    Args:
            session_id: The session ID to archive

    Returns:
            dict: Success status
    """
    _validate_session_id(session_id)
    try:
        user = frappe.session.user

        # Verify the session belongs to the current user
        count = frappe.db.count("PA Chat Message", {"session_id": session_id, "user": user})
        if not count:
            return {"success": False, "error": _("Session not found or access denied")}

        # Archive locally — mark all messages, preserve data
        frappe.db.set_value(
            "PA Chat Message",
            {"session_id": session_id, "user": user},
            "is_archived",
            1,
            update_modified=False,
        )

        # Delete-with-messages: drop the zero-retention session blob so it never
        # outlives the conversation it belongs to (no separate TTL).
        PAChatSessionState.delete_for_sessions(session_id)

        return {"success": True, "archived_count": count}

    except Exception as e:
        frappe.log_error(title="AIDA Session Archive Error", message=f"Error archiving session: {e!s}")
        return {"success": False, "error": _safe_error(e, "AIDA Session Archive Error")}


@frappe.whitelist(methods=["POST"])
def delete_session(session_id: str) -> dict:
    """
    Archive a session (backward compatibility wrapper for mobile).

    Calls archive_session() internally — local data is preserved,
    AR-side data is hard-deleted.
    """
    return archive_session(session_id)


@frappe.whitelist(methods=["POST"])
def archive_all_conversations() -> dict:
    """
    Archive all conversations for the current user.

    Marks all local PA Chat Messages as archived and drops each session's
    zero-retention state blob. Under the stateless default AR holds no
    conversation to delete, so cleanup is purely local.

    Returns:
            dict: Success status with count of archived messages
    """
    try:
        user = frappe.session.user

        # Get distinct session IDs before archiving
        session_ids = frappe.get_all(
            "PA Chat Message",
            filters={"user": user, "is_archived": 0, "session_id": ["is", "set"]},
            pluck="session_id",
            distinct=True,
            limit_page_length=0,
        )

        if not session_ids:
            return {"success": True, "archived_count": 0}

        archived_count = frappe.db.count("PA Chat Message", {"user": user, "is_archived": 0})

        # Archive all local messages
        frappe.db.set_value(
            "PA Chat Message",
            {"user": user, "is_archived": 0},
            "is_archived",
            1,
            update_modified=False,
        )

        # Delete-with-messages: drop every zero-retention session blob in one
        # pass. Without this, bulk "Archive all" orphans every state row.
        PAChatSessionState.delete_for_sessions(session_ids)

        return {"success": True, "archived_count": archived_count}

    except Exception as e:
        frappe.log_error(title="AIDA Archive All Error", message=f"Error archiving conversations: {e!s}")
        return {"success": False, "error": _safe_error(e, "AIDA Archive All Error")}


@frappe.whitelist(methods=["POST"])
def clear_all_conversations() -> dict:
    """Backward compatibility — now archives instead of deleting."""
    return archive_all_conversations()


@frappe.whitelist(methods=["GET"])
def get_archived_sessions(limit: int = 50) -> list:
    """
    Get user's archived chat sessions.

    Returns:
            list: Archived sessions with session_id, preview, started, last_activity
    """
    limit = _int_param(limit, 50, 1, 100)
    try:
        sessions = _sessions_with_previews(frappe.session.user, 1, limit, _("Archived conversation"))
        for session in sessions:
            session["is_archived"] = True
        return sessions

    except Exception as e:
        frappe.log_error(
            title="AIDA Archived Sessions Error", message=f"Error getting archived sessions: {e!s}"
        )
        return []


@frappe.whitelist(methods=["POST"])
def continue_archived_session(old_session_id: str) -> dict:
    """
    Create a new session with context from an archived conversation.

    Loads recent messages from the archived session and formats them as
    a context addendum that can be passed as system_prompt_addendum on
    the first message in the new session, giving the agent prior context.

    Args:
            old_session_id: The archived session to continue from

    Returns:
            dict: { new_session_id, context_addendum }
    """
    import uuid

    _validate_session_id(old_session_id)
    try:
        user = frappe.session.user

        # Load recent messages from the archived session
        messages = frappe.get_all(
            "PA Chat Message",
            filters={
                "session_id": old_session_id,
                "user": user,
                "is_archived": 1,
            },
            fields=["role", "content", "creation"],
            order_by="creation desc",
            limit_page_length=20,
        )

        if not messages:
            return {"success": False, "error": _("Archived session not found")}

        # Reverse to chronological order
        messages.reverse()

        # Build context addendum from message history.
        # Wrap the transcript in an untrusted envelope so the LLM doesn't
        # treat archived USER/ASSISTANT lines as instructions
        # (AIDA-H15 / AIDA-M10 prompt injection via history).
        history_lines = []
        for msg in messages:
            content = (msg.content or "")[:2000]
            role_label = "USER" if msg.role == "user" else "ASSISTANT"
            history_lines.append(f"{role_label}: {content}")

        transcript = "\n\n".join(history_lines)
        context_addendum = (
            "## Prior Conversation Context\n"
            "The user is continuing a previous conversation. "
            "Here is the recent history:"
            + wrap_untrusted(transcript, kind="prior_conversation")
            + "\nContinue naturally from this context. "
            "The user may reference things discussed above."
        )

        # Create a new session
        new_session_id = str(uuid.uuid4())

        return {
            "success": True,
            "new_session_id": new_session_id,
            "context_addendum": context_addendum,
            "messages_included": len(messages),
        }

    except Exception as e:
        frappe.log_error(
            title="AIDA Continue Archived Error", message=f"Error continuing archived session: {e!s}"
        )
        return {"success": False, "error": _safe_error(e, "AIDA Continue Archived Error")}
