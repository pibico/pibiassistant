# pibiAssistant - AIDA relay entry points
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Background-thread entry points of the chat relay.

These functions run in the bounded ``_relay_pool`` defined in ``messages``.
They re-establish a Frappe context on entry and tear it down on exit, and hand
the turn to the native AIDA relay (``aida_stream``). Also hosts the persistence
helpers shared with ``aida_stream`` and ``cancel``. Not whitelisted endpoints.
"""

from __future__ import annotations

import time

import frappe
from frappe import _

from .._helpers import (
    _not_registered_error,
    _safe_error,
)
from ..chat.cancel import (
    append_abort_marker,
    clear as clear_cancel,
)
from ..chat.helpers import (
    _emit_socket_event,
    _find_assistant_msg_by_message_id,
)


def _set_pao_message_with_retry(name: str, updates: dict, *, attempts: int = 3) -> bool:
    """Update a AIDA Message row, retrying on InnoDB record-changed (1020).

    The streaming relay and the cancel path both write to the same row
    (blocks/content). When the user presses Stop while a resume is mid-
    flight, those two writers can race; MariaDB raises
    ``QueryDeadlockError(1020, "Record has changed since last read")``
    from its optimistic concurrency check. Retrying with a fresh read
    resolves it without losing data: the second writer simply re-applies
    its updates on top of the first writer's row.

    Returns True on success, False if all attempts failed.
    """
    for attempt in range(attempts):
        try:
            frappe.db.set_value("PA Chat Message", name, updates)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context
            return True
        except frappe.QueryDeadlockError:
            frappe.db.rollback()
            if attempt == attempts - 1:
                frappe.log_error(
                    title="PA Chat Message write contention",
                    message=(
                        f"set_value retry exhausted for {name} after {attempts} attempts. "
                        f"Update keys: {list(updates.keys())}"
                    ),
                )
                return False
            # Brief backoff lets the other writer's transaction commit so
            # the next read sees a stable row.
            time.sleep(0.05 * (attempt + 1))
    return False



def _relay_ar_interrupt_resume(
    session_id,
    interrupt_response,
    user,
    site,
    client_type=None,
    message_id=None,
    session_state=None,
    restricted=False,
    model_id=None,
    web_search=None,
    thinking_enabled=None,
):
    """Resume an interrupted AIDA turn with the user's approval responses.

    Runs in a background thread. ``client_type`` / ``session_state`` /
    ``web_search`` / ``thinking_enabled`` are accepted for call-site
    compatibility with ``messages.resume_interrupt`` and are unused by AIDA.
    """
    frappe.init(site=site)
    frappe.connect()
    # Background-thread context re-establishment: `user` propagated from the
    # outer request handler, never client input.
    frappe.set_user(user)  # nosemgrep: frappe-setuser

    # A cancel flag set before this resume started (Stop pressed during the
    # prior pause, or racing a turn that was already completing) can never
    # legitimately apply to a turn that hasn't started yet.
    clear_cancel(session_id)

    try:
        from .aida_stream import _relay_aida_stream, is_aida_mode, release_turn
        from .aida_tools import peek_pending

        if not is_aida_mode():
            _emit_socket_event(
                session_id,
                {
                    "event": "stream_error",
                    "session_id": session_id,
                    "error": _not_registered_error(),
                    "action_required": "register",
                },
            )
            return

        try:
            pending = peek_pending(session_id, user)
            if not pending:
                _emit_socket_event(
                    session_id,
                    {
                        "event": "stream_error",
                        "session_id": session_id,
                        "error": _("There is nothing pending to approve in this conversation."),
                    },
                )
                return
            _relay_aida_stream(
                session_id,
                "",
                None,
                user,
                restricted=restricted,
                continue_from_message_id=pending["message_id"],
                model_id=model_id,
                resume_responses=[r for r in (interrupt_response or []) if isinstance(r, dict)],
            )
        finally:
            release_turn(session_id)

    except Exception as e:
        import traceback

        frappe.log_error(
            title="AIDA Stream Error",
            message=f"Error in interrupt resume relay: {e!s}\n{traceback.format_exc()}",
        )
        _emit_socket_event(
            session_id,
            {
                "event": "stream_error",
                "session_id": session_id,
                "error": _safe_error(e, "AIDA Chat Error"),
                "message_id": None,
                "blocks": [],
                "partial_response": "",
            },
        )

    finally:
        # Clear cancel marker so the same session can stream again. Safe
        # even when no cancel was issued — delete_value() on an absent
        # Redis key is a no-op.
        clear_cancel(session_id)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.
        frappe.destroy()


def _relay_ar_stream(
    session_id,
    full_prompt,
    original_message,
    context,
    message_name,
    user,
    site,
    model_id=None,
    attachments=None,
    system_prompt_addendum=None,
    client_type=None,
    session_state=None,
    restricted=False,
    continue_from_message_id=None,
    web_search=None,
    thinking_enabled=None,
    extract_files=False,
):
    """Relay one AIDA turn (new message or continuation) to the SPA via Socket.IO.

    Runs in a background thread: sets up the Frappe context, hands the turn to
    ``aida_stream._relay_aida_stream`` and tears the context down. The
    ``full_prompt`` / ``attachments`` / ``client_type`` / ``session_state`` /
    ``web_search`` / ``thinking_enabled`` parameters are accepted for call-site
    compatibility with ``messages`` and are unused by AIDA.
    """
    frappe.init(site=site)
    frappe.connect()
    # Background-thread context re-establishment.
    frappe.set_user(user)  # nosemgrep: frappe-setuser

    # The stale cancel flag is cleared by send_message/continue_response in the
    # request thread; clearing it here would wipe a Stop pressed while queued.

    try:
        from .aida_stream import _relay_aida_stream, is_aida_mode, release_turn

        if not is_aida_mode():
            _emit_socket_event(
                session_id,
                {
                    "event": "stream_error",
                    "session_id": session_id,
                    "error": _not_registered_error(),
                    "action_required": "register",
                },
            )
            return

        try:
            _relay_aida_stream(
                session_id,
                original_message,
                message_name,
                user,
                restricted=restricted,
                system_prompt_addendum=system_prompt_addendum,
                context=context,
                continue_from_message_id=continue_from_message_id,
                model_id=model_id,
                extract_files=extract_files,
            )
        finally:
            release_turn(session_id)

    except Exception as e:
        import traceback

        frappe.log_error(
            title="AIDA Stream Error",
            message=f"Error in stream relay: {e!s}\n{traceback.format_exc()}",
        )
        _emit_socket_event(
            session_id,
            {
                "event": "stream_error",
                "session_id": session_id,
                "error": _safe_error(e, "AIDA Stream Error"),
                "message_id": None,
                "blocks": [],
                "partial_response": "",
            },
        )

    finally:
        # Clear cancel marker so the same session can stream again.
        # Safe even when no cancel was issued — delete_value() on an absent
        # Redis key is a no-op.
        clear_cancel(session_id)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.
        frappe.destroy()


def _persist_partial_assistant_turn(
    session_id: str,
    ar_message_id: str | None,
    partial_response: str,
    blocks_snapshot: list,
    collected_tool_calls: list,
    model_used: str,
    flag_field: str,
) -> str | None:
    """Persist whatever the agent produced so far, marking the row with
    ``flag_field`` (``"aborted"`` or ``"errored"``) so a reload renders the
    truncated turn instead of losing it.

    Three lookup tiers, because in practice we've observed AIDA Messages
    missing ``message_id`` on the row that stream_start was supposed to
    create (stream_start either didn't carry message_id, or
    _ensure_assistant_msg silently failed). Without these fallbacks the
    write was a no-op and the reload was empty:

      1. Look up by message_id (the canonical key).
      2. Fall back to the most recent assistant row in this session whose
         message_id is NULL — that's the row stream_start would have
         created (or stream_complete would have created via _log_conversation).
      3. If no row exists at all (interruption before AR persisted anything),
         create one now so a reload still shows the partial + marker.

    Returns the PA Chat Message name that was written, or None if nothing
    could be persisted.
    """
    import json as _json_mod

    assistant_row = _find_assistant_msg_by_message_id(session_id, ar_message_id) if ar_message_id else None
    if not assistant_row and not ar_message_id:
        # Tier 2 (legacy, no message_id): most recent assistant row in this session. With a
        # message_id it would overwrite the previous turn's answer, so a new row is created instead.
        assistant_row = frappe.db.get_value(
            "PA Chat Message",
            {"session_id": session_id, "role": "assistant"},
            "name",
            order_by="creation desc",
        )
    if not assistant_row:
        # Tier 3: no row exists yet. Create one so the partial is visible on reload.
        try:
            from pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message import (
                PAChatMessage,
            )

            msg = PAChatMessage.create_message(
                session_id=session_id,
                role="assistant",
                content=partial_response or "",
            )
            if msg:
                assistant_row = msg.name
                if ar_message_id:
                    frappe.db.set_value("PA Chat Message", assistant_row, "message_id", ar_message_id)
        except Exception as e:
            frappe.log_error(
                title="PA Stream Partial Persist",
                message=f"Failed to create PA Chat Message for {session_id}: {e!s}",
            )

    if assistant_row:
        updates = {
            "content": partial_response,
            "blocks": _json_mod.dumps(blocks_snapshot),
            flag_field: 1,
        }
        # Backfill message_id if we have it and the row is missing it. This
        # also future-proofs against the upstream stream_start/message_id
        # bug — once the row gets the id, subsequent lookups work.
        if ar_message_id:
            updates["message_id"] = ar_message_id
        if model_used:
            updates["model"] = model_used
        if collected_tool_calls:
            updates["tool_calls"] = _json_mod.dumps(collected_tool_calls)
        _set_pao_message_with_retry(assistant_row, updates)

    return assistant_row


def _handle_stream_aborted(
    session_id: str,
    ar_message_id: str | None,
    partial_response: str,
    block_builder,
    collected_tool_calls: list,
    model_used: str,
    stream_iter,
) -> None:
    """Persist whatever the agent produced before the user pressed Stop,
    then emit ``stream_aborted`` so the SPA can finalize its UI state.

    Three things happen here, in order:

    1. Close the SDK iterator. ``stream_chat`` is a generator over an
       HTTP/SSE response; calling ``.close()`` drops the connection,
       which is the signal AR uses to tear down its agent loop. Without
       this, the agent keeps running on the backend and we keep paying
       for tokens we'll never show.
    2. Save the partial assistant turn with ``aborted=1``, the "(Stopped
       by user)" marker appended. The blocks snapshot already reflects
       everything received up to this point, so a reload will render the
       truncated answer correctly rather than vanishing or appearing
       "still streaming".
    3. Emit ``stream_aborted`` so the streamManager on the SPA can
       flip ``isStreaming=false``, clear its activity timeout, and
       render the "(Stopped by user)" tail.
    """
    # Step 1 — drop the upstream connection.
    try:
        stream_iter.close()
    except Exception as e:
        # Closing a half-drained generator can raise; don't let that
        # block the persistence + event emission we still need to do.
        frappe.logger("pao.chat.cancel").warning(
            f"stream_iter.close() raised during abort for {session_id}: {e}"
        )

    # Step 2 — persist the partial with the marker. cancel_stream's own
    # HITL-pause finalizer (cancel.py:_abort_pending_interactions) races
    # this on the same row; append_abort_marker is idempotent so whichever
    # of the two writers gets here first adds the marker and the other is
    # a safe no-op.
    marked_response, blocks_snapshot = append_abort_marker(partial_response, block_builder.snapshot())
    _persist_partial_assistant_turn(
        session_id,
        ar_message_id,
        marked_response,
        blocks_snapshot,
        collected_tool_calls,
        model_used,
        "aborted",
    )

    # Step 3 — tell the SPA we're done.
    _emit_socket_event(
        session_id,
        {
            "event": "stream_aborted",
            "session_id": session_id,
            "message_id": ar_message_id,
            "partial_response": marked_response,
            "blocks": blocks_snapshot,
        },
    )
