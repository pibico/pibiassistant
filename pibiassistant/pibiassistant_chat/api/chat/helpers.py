# pibiAssistant - Chat Internal Helpers
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Internal helpers shared by messaging and AR-relay paths.

None of these are whitelisted endpoints — they're called from the
streaming background-thread relay and the send/resume request handlers.
"""

from __future__ import annotations

import frappe


def _is_processing_restricted(user: str | None = None) -> bool:
    """AIDA-M15: return True when the user has set GDPR Art. 18 restriction.

    Reads the local mirror on AIDA User Preferences (kept in sync by
    ``privacy.restrict_my_processing``). Defaults to False (persist normally)
    when the preferences row doesn't exist or the column hasn't been migrated
    yet — fail-open is the right call here because the alternative is to
    silently drop chat history for every user on upgrade day.
    """
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False
    try:
        flag = frappe.db.get_value("PA Chat User Preferences", user, "processing_restricted")
        return bool(flag)
    except Exception:
        return False


def _emit_socket_event(session_id, data):
    """Emit a Socket.IO event scoped to a single session room.

    Clients (widget + SPA) join the matching ``task_progress:<id>`` room via
    Frappe's ``task_subscribe`` socket event when they start a session, so
    events for one tab/conversation never reach other tabs the same user has
    open. We pass ``room=`` directly (rather than ``task_id=``) because it is
    more explicit about scoping — these aren't real background tasks.
    """
    try:
        frappe.publish_realtime(
            event="pao_message_stream",
            message=data,
            room=f"task_progress:{session_id}",
            after_commit=False,
        )
    except Exception as e:
        frappe.log_error(title="AIDA Socket Error", message=f"Error emitting socket event: {e!s}")


def _attach_files_to_message(file_urls: list[str], message_name: str) -> int:
    """Link composer uploads to the persisted user message. Returns the count linked.

    Ownership scoping is the security boundary here: ``get_all`` bypasses
    permissions, so without ``owner`` any caller could name an arbitrary private
    ``file_url`` and have ``_extract_file_attachments`` read it into the prompt.

    Only pending composer uploads qualify: a file the caller owns that is already attached
    to a business document must not be moved off it.

    Clearing ``pa_pending_chat_attachment`` is what takes the file out of the
    orphan sweep's reach — uploads are flagged on selection, not on send.
    """
    file_docs = frappe.get_all(
        "File",
        filters={"file_url": ["in", file_urls], "owner": frappe.session.user, "pa_pending_chat_attachment": 1},
        fields=["name", "file_url"],
        limit_page_length=0,
    )

    linked = 0
    for file_doc in file_docs:
        try:
            frappe.db.set_value(
                "File",
                file_doc.name,
                {
                    "attached_to_doctype": "PA Chat Message",
                    "attached_to_name": message_name,
                    "pa_pending_chat_attachment": 0,
                },
                update_modified=False,
            )
            linked += 1
        except Exception as e:
            frappe.log_error(
                title="AIDA File Attachment Error",
                message=f"Error attaching file {file_doc.file_url}: {e!s}",
            )

    frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.
    return linked


MAX_FILE_CHARS = 30000
MAX_ATTACHMENT_CHARS = 60000
_TRUNCATED = "\n[... truncated: the file is longer than what fits in the prompt; ask for a specific part ...]"


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + _TRUNCATED


def _describe_file(extractor, file_info) -> str:
    """The prompt block for one attached file; a failed read becomes a note the model can relay."""
    try:
        result = extractor.execute({"file_url": file_info.file_url, "operation": "extract"})

        if result.get("success") and result.get("content"):
            size_bytes = file_info.file_size or 0
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

            return "\n".join(
                [
                    f"\nFile: {file_info.file_name}",
                    f"URL: {file_info.file_url}",
                    f"Size: {size_str}",
                    "Content:",
                    _clip(result["content"], MAX_FILE_CHARS),
                    "-" * 80,
                ]
            )
        return (
            f"\nFile: {file_info.file_name}\nURL: {file_info.file_url}\n"
            f"The content of this file could not be read: {result.get('error') or 'unknown error'}"
        )

    except Exception as e:
        frappe.log_error(
            title="AIDA File Extraction",
            message=f"Error extracting file {file_info.file_name}: {e!s}",
        )
        return (
            f"\nFile: {file_info.file_name}\nURL: {file_info.file_url}\n"
            "The content of this file could not be read."
        )


def _describe_file_in_own_context(site: str, user: str, file_info) -> str:
    """_describe_file in a worker thread: Frappe's context is per thread, so open a private one."""
    frappe.init(site=site)
    frappe.connect()
    try:
        frappe.set_user(user)  # nosemgrep: frappe-setuser
        from pibiassistant.plugins.data_science.tools.extract_file_content import ExtractFileContent

        return _describe_file(ExtractFileContent(), file_info)
    finally:
        frappe.destroy()


def _extract_file_attachments(message_name: str, parallel: bool = False) -> str:
    """
    Extract content from files attached to a AIDA Message.

    Uses the ExtractFileContent tool from pibiassistant. Each file is clipped to
    ``MAX_FILE_CHARS`` and the whole block to ``MAX_ATTACHMENT_CHARS``. With
    ``parallel`` the files are converted concurrently (the conversion service is
    the slow part), each in its own Frappe context.
    """
    try:
        attached_files = frappe.get_all(
            "File",
            filters={"attached_to_doctype": "PA Chat Message", "attached_to_name": message_name},
            fields=["name", "file_name", "file_url", "file_size"],
        )

        if not attached_files:
            return ""

        try:
            from pibiassistant.plugins.data_science.tools.extract_file_content import (
                ExtractFileContent,
            )

            extractor = ExtractFileContent()
        except ImportError:
            frappe.log_error(title="AIDA File Extraction", message="pibiassistant not installed")
            return ""

        if parallel and len(attached_files) > 1:
            from concurrent.futures import ThreadPoolExecutor

            site, user = frappe.local.site, frappe.session.user
            with ThreadPoolExecutor(max_workers=min(len(attached_files), 4)) as pool:
                blocks = list(
                    pool.map(lambda f: _describe_file_in_own_context(site, user, f), attached_files)
                )
        else:
            blocks = [_describe_file(extractor, f) for f in attached_files]

        out, budget = [], MAX_ATTACHMENT_CHARS
        for block in blocks:
            if budget <= 0:
                out.append("\nFurther attached files were left out: the prompt size limit was reached.")
                break
            out.append(_clip(block, budget))
            budget -= len(block)
        return "\n".join(["[Attached Files]", *out]) if out else ""

    except Exception as e:
        frappe.log_error(
            title="AIDA File Extraction Error", message=f"Error in _extract_file_attachments: {e!s}"
        )
        return ""


def _find_assistant_msg_by_message_id(session_id: str, message_id: str) -> str | None:
    """Find the AIDA Message row for a specific assistant turn, keyed on AR's message_id.

    message_id is AR's per-turn identifier and stays stable across HITL
    interrupt/resume cycles within the same turn (AR reuses it). This
    avoids the "find most recent assistant row" trap that appended resume
    output to the wrong turn after a prior completed turn's row became the
    most recent. Returns the AIDA Message `name` or None.
    """
    if not message_id:
        return None
    return frappe.db.get_value(
        "PA Chat Message",
        {"session_id": session_id, "role": "assistant", "message_id": message_id},
        "name",
    )


def _ensure_assistant_msg(session_id: str, message_id: str, context: dict | None = None) -> str | None:
    """Create the assistant AIDA Message row early so resumes can find it by message_id.

    Called on ``stream_start`` in ``_relay_ar_stream``. The row begins with
    empty content and is updated in place when ``stream_complete`` fires
    (even if the stream ends with ``interrupted=True``, a row exists for
    the next resume to find). Idempotent — returns an existing row if one
    is already keyed on this message_id.
    """
    if not message_id:
        return None

    existing = _find_assistant_msg_by_message_id(session_id, message_id)
    if existing:
        return existing

    try:
        from pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message import (
            PAChatMessage,
        )

        msg = PAChatMessage.create_message(
            session_id=session_id,
            role="assistant",
            content="",
            context=context,
        )
        if msg and message_id:
            frappe.db.set_value("PA Chat Message", msg.name, "message_id", message_id)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.
            return msg.name
    except Exception as e:
        frappe.log_error(title="AIDA Log Error", message=f"Error ensuring assistant message row: {e!s}")
    return None
