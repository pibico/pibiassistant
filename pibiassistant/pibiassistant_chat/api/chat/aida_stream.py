# pibiAssistant - Native AIDA stream relay
# AGPL-3.0 License

"""Relay the AIDA Chat API (api.espib.co) SSE stream to the SPA via Socket.IO.

Runs inside an already-connected background-thread Frappe context (see
``relay._relay_ar_stream``), which owns ``frappe.connect`` / ``destroy``. It
never talks to the PA Cloud service.
"""

from __future__ import annotations

import json
import time
import uuid

import frappe
import requests
from frappe import _

from .._untrusted import wrap_untrusted
from .._helpers import is_aida_mode  # noqa: F401  (re-exported for messages/relay)
from ..chat.cancel import append_abort_marker, is_cancelled
from .aida_tools import recent_turns
from ..chat.helpers import _emit_socket_event, _ensure_assistant_msg, _find_assistant_msg_by_message_id

_STATE_SIG = "aida-conversation"
# (connect, read): read bounds the gap between SSE lines, which is also how
# often the Stop flag gets a chance to be polled while the model is silent.
_TIMEOUT = (10, 90)
_TURN_LOCK_TTL = 600


def _turn_lock_key(session_id: str) -> str:
    return frappe.cache().make_key(f"pa_aida_turn:{session_id}")


def acquire_turn(session_id: str) -> bool:
    """Claim the single in-flight turn of a session (atomic; expires if the relay dies)."""
    return bool(frappe.cache().set(_turn_lock_key(session_id), "1", nx=True, ex=_TURN_LOCK_TTL))


def acquire_turn_waiting(session_id: str, wait_s: float = 3.0) -> bool:
    """acquire_turn, but tolerate the second or so a cancelled relay needs to notice Stop and release."""
    if acquire_turn(session_id):
        return True
    if not is_cancelled(session_id):
        return False
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        time.sleep(0.1)
        if acquire_turn(session_id):
            return True
    return False


def refresh_turn(session_id: str) -> None:
    """Keep the lock alive while the relay still produces events (tool turns outlast the TTL)."""
    try:
        frappe.cache().expire(_turn_lock_key(session_id), _TURN_LOCK_TTL)
    except Exception:
        pass


def is_turn_active(session_id: str) -> bool:
    return bool(frappe.cache().get(_turn_lock_key(session_id)))


def release_turn(session_id: str) -> None:
    try:
        frappe.cache().delete(_turn_lock_key(session_id))
    except Exception:
        pass


def get_conversation_id(session_id: str) -> str | None:
    row = frappe.db.get_value(
        "PA Chat Session State",
        {"session_id": session_id, "state_sig": _STATE_SIG},
        "state_blob",
    )
    return row or None


def set_conversation_id(session_id: str, user: str, conversation_id: str | None) -> None:
    """Persist the AIDA conversation_id for a session (reuses PA Chat Session State)."""
    if not conversation_id:
        return
    name = frappe.db.exists("PA Chat Session State", {"session_id": session_id})
    values = {
        "state_blob": conversation_id,
        "state_sig": _STATE_SIG,
        "format_version": 1,
        "updated_at": frappe.utils.now(),
    }
    if name:
        frappe.db.set_value("PA Chat Session State", name, values)
    else:
        frappe.get_doc(
            {"doctype": "PA Chat Session State", "session_id": session_id, "user": user, "turn_seq": 0, **values}
        ).insert(ignore_permissions=True)
    frappe.db.commit()  # nosemgrep: frappe-manual-commit — background relay thread


def clear_conversation_id(session_id: str) -> None:
    name = frappe.db.exists("PA Chat Session State", {"session_id": session_id, "state_sig": _STATE_SIG})
    if name:
        frappe.delete_doc("PA Chat Session State", name, ignore_permissions=True, force=True)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — background relay thread


def _build_transcript(session_id: str, exclude_name: str | None) -> str:
    """Compact transcript of earlier turns, for sessions that have no AIDA conversation_id yet."""
    lines = [
        f"{'USER' if role == 'user' else 'ASSISTANT'}: {text}"
        for role, text in recent_turns(session_id, exclude_name)
    ]
    if not lines:
        return ""
    return (
        "## Prior Conversation Context\nThe user is continuing a conversation. Recent history:"
        + wrap_untrusted("\n\n".join(lines), kind="prior_conversation")
        + "\nContinue naturally from it.\n\n"
    )


def _friendly_error(status: int | None = None, exc: Exception | None = None) -> str:
    if isinstance(exc, requests.exceptions.Timeout):
        return _("AIDA took too long to respond. Please try again.")
    if isinstance(exc, requests.exceptions.ConnectionError):
        return _("Cannot connect to AIDA right now. Please try again in a moment.")
    if status in (401, 403):
        return _("AIDA rejected the API key. Ask your administrator to check the AIDA settings.")
    if status == 429:
        return _("AIDA is receiving too many requests. Please wait a moment and try again.")
    return _("AIDA could not answer right now. Please try again.")


def _iter_events(resp):
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        try:
            event = json.loads(data)
        except ValueError:
            continue
        if isinstance(event, dict):
            yield event


def _iter_events_polled(resp, session_id):
    """Yield SSE events; yield None every second of silence so Stop is honoured promptly."""
    import queue
    import threading

    q: queue.Queue = queue.Queue()
    stop = threading.Event()
    end = object()

    def reader():
        try:
            for ev in _iter_events(resp):
                if stop.is_set():
                    return
                q.put(ev)
            q.put(end)
        except Exception as exc:
            q.put(exc)

    threading.Thread(target=reader, daemon=True).start()
    try:
        while True:
            try:
                item = q.get(timeout=1)
            except queue.Empty:
                yield None
                continue
            if item is end:
                return
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        stop.set()


def _open_stream(url, headers, body):
    return requests.post(url, json=body, headers=headers, stream=True, timeout=_TIMEOUT)


def _relay_aida_stream(
    session_id,
    message,
    message_name,
    user,
    restricted=False,
    system_prompt_addendum=None,
    context=None,
    continue_from_message_id=None,
    model_id=None,
    resume_responses=None,
    extract_files=False,
):
    """Stream one AIDA turn to the SPA, persisting the assistant row unless restricted."""
    from ..block_builder import BlockBuilder
    from ..chat.relay import _handle_stream_aborted, _persist_partial_assistant_turn, _set_pao_message_with_retry
    from ..aida import _get_aida_config

    api_url, api_key, provider, model = _get_aida_config()
    chosen = (model_id or "").strip()[:200]
    if chosen and chosen != "auto":
        # The selector sends "provider/model"; a bare name keeps the default provider.
        if "/" in chosen:
            provider, model = chosen.split("/", 1)
        else:
            model = chosen
    try:
        import frappe.translate

        frappe.local.lang = frappe.translate.get_user_lang(user)
    except Exception:
        pass
    block_builder = BlockBuilder()
    message_id = continue_from_message_id or uuid.uuid4().hex[:10]
    full_response = ""
    model_used = model or ""
    resp = None
    prefix = ""

    def emit(payload):
        refresh_turn(session_id)
        _emit_socket_event(session_id, {"session_id": session_id, **payload})

    def fail(text):
        emit(
            {
                "event": "stream_error",
                "error": text,
                "message_id": message_id,
                "blocks": block_builder.snapshot(),
                "partial_response": full_response,
            }
        )
        if not restricted:
            _persist_partial_assistant_turn(
                session_id,
                message_id,
                full_response or text,
                block_builder.snapshot() or [{"type": "text", "id": f"err-{message_id}", "content": text}],
                [],
                model_used,
                "errored",
            )

    try:
        if not restricted and not continue_from_message_id:
            _ensure_assistant_msg(session_id, message_id, context)
        if not api_url or not api_key:
            fail(_("AIDA is not configured. Ask your administrator to set it up in PA Core Settings."))
            return

        if continue_from_message_id and not restricted:
            row = frappe.db.get_value(
                "PA Chat Message",
                {"session_id": session_id, "role": "assistant", "message_id": continue_from_message_id},
                ["content", "blocks"],
                as_dict=True,
            )
            if row and row.blocks:
                try:
                    block_builder = BlockBuilder(existing_blocks=json.loads(row.blocks))
                except ValueError:
                    pass
            prefix = (row.content if row else "") or ""
            full_response = prefix
            message = _("Continue your previous answer exactly where it stopped.")

        conversation_id = None if restricted else get_conversation_id(session_id)
        user_text = message or ""
        if system_prompt_addendum:
            user_text = f"{system_prompt_addendum}\n\n{user_text}"

        def make_body(conv_id):
            text = user_text
            if not conv_id and not restricted:
                text = _build_transcript(session_id, message_name) + text
            body = {"message": text, "stream": True}
            if conv_id:
                body["conversation_id"] = conv_id
            if provider:
                body["provider"] = provider
            if model:
                body["model"] = model
            return body

        headers = {"X-API-Key": api_key, "Content-Type": "application/json", "Accept": "text/event-stream"}
        url = f"{api_url}/api/v1/chat/completions"

        emit(
            {
                "event": "stream_start",
                "message_id": message_id,
                "model_id": model_used,
                **({"resumed": True} if resume_responses is not None else {}),
            }
        )

        if extract_files and message_name and not restricted:
            # Converting attachments is the slow part of a turn; it runs here, after the UI got
            # stream_start, so the send request itself never waits on the conversion service.
            from .helpers import _extract_file_attachments

            file_content = _extract_file_attachments(message_name, parallel=True)
            if file_content:
                system_prompt_addendum = (system_prompt_addendum or "") + wrap_untrusted(
                    file_content, kind="user_attached_files"
                )
                user_text = f"{system_prompt_addendum}\n\n{message or ''}"

        finish_reason = None
        tokens = {}
        done = False
        started_at = time.monotonic()
        new_chars = 0
        tool_calls_log = []
        tool_done = False

        from .aida_tools import chat_tool_specs, chunk_text, resume_tool_turn, run_tool_turn, tools_enabled

        resuming = resume_responses is not None
        outcome = None
        if model and tools_enabled() and (resuming or not continue_from_message_id):
            try:
                specs = chat_tool_specs(user)
                if resuming:
                    block_builder.resolve_pending_interactions(resume_responses)
                    outcome = resume_tool_turn(
                        session_id=session_id,
                        user=user,
                        responses=resume_responses,
                        api_url=api_url,
                        api_key=api_key,
                        specs=specs,
                        emit=emit,
                        block_builder=block_builder,
                    )
                elif specs:
                    outcome = run_tool_turn(
                        session_id=session_id,
                        user=user,
                        message=user_text,
                        message_name=message_name,
                        message_id=message_id,
                        api_url=api_url,
                        api_key=api_key,
                        provider=provider,
                        model=model,
                        specs=specs,
                        emit=emit,
                        block_builder=block_builder,
                    )
            except Exception as e:
                frappe.log_error(title="AIDA Tool Turn Error", message=str(e)[:500])
                # Once a tool has run its result is only in this turn: a plain re-run would answer blind
                # (or repeat a change), so surface the failure instead.
                if resuming or block_builder.snapshot():
                    fail(_friendly_error(exc=e if isinstance(e, requests.exceptions.RequestException) else None))
                    return
            if outcome and outcome.get("expired"):
                fail(_("This approval has expired. Please ask again."))
                return
            if outcome and outcome.get("aborted"):
                if restricted:
                    _abort_unpersisted(emit, message_id, full_response, block_builder)
                else:
                    _handle_stream_aborted(session_id, message_id, full_response, block_builder, [], model_used, None)
                return
            if outcome and outcome.get("text"):
                model_used = outcome["model"] or model_used
                text_out = ("\n\n" + outcome["text"]) if prefix.strip() and not new_chars else outcome["text"]
                for piece in chunk_text(text_out):
                    full_response += piece
                    new_chars += len(piece)
                    block_builder.add_text(piece)
                    emit({"event": "stream_chunk", "chunk": piece, "accumulated": full_response, "message_id": message_id})
            if outcome and (outcome.get("text") or outcome.get("interrupted")):
                model_used = outcome["model"] or model_used
                tokens = {
                    "prompt_tokens": outcome["prompt_tokens"],
                    "completion_tokens": outcome["completion_tokens"],
                }
                tool_calls_log = outcome["tool_calls"]
                done = True
                tool_done = True
            if outcome and outcome.get("interrupted"):
                usage = {
                    "prompt_tokens": int(tokens.get("prompt_tokens") or 0),
                    "completion_tokens": int(tokens.get("completion_tokens") or 0),
                    "duration_ms": int((time.monotonic() - started_at) * 1000),
                }
                pending_ids = []
                for item in outcome["pending"]:
                    block_builder.add_approval_required(
                        item["tool_id"], item["tool_name"], item["input"], item["interrupts"]
                    )
                    pending_ids += [i["id"] for i in item["interrupts"]]
                    emit(
                        {
                            "event": "approval_required",
                            "tool_id": item["tool_id"],
                            "tool_name": item["tool_name"],
                            "input": item["input"],
                            "interrupts": item["interrupts"],
                            "expires_at": frappe.utils.add_to_date(None, seconds=1800, as_string=True),
                        }
                    )
                if not restricted:
                    row = _find_assistant_msg_by_message_id(session_id, message_id)
                    if row:
                        _set_pao_message_with_retry(
                            row,
                            {
                                "content": full_response,
                                "blocks": json.dumps(block_builder.snapshot()),
                                "model": model_used or None,
                                "credits_used": 0,
                                **usage,
                                **({"tool_calls": json.dumps(tool_calls_log)} if tool_calls_log else {}),
                            },
                        )
                emit(
                    {
                        "event": "stream_complete",
                        "message_id": message_id,
                        "full_response": full_response,
                        "model_id": model_used,
                        "blocks": block_builder.snapshot(),
                        "interrupted": True,
                        "pending_interrupts": pending_ids,
                        "quota_remaining": -1,
                        "quota_used": 0,
                        "quota_total": -1,
                        "credits_used": 0,
                        **usage,
                    }
                )
                return

        if (resuming or (outcome and outcome.get("tool_calls"))) and not tool_done:
            fail(_("AIDA returned an empty answer. Please try again."))
            return

        if not tool_done:
            resp = _open_stream(url, headers, make_body(conversation_id))
            if conversation_id and resp.status_code in (400, 404, 422):
                # Upstream forgot the conversation: start fresh from the local transcript.
                resp.close()
                clear_conversation_id(session_id)
                conversation_id = None
                resp = _open_stream(url, headers, make_body(None))
            if resp.status_code != 200:
                frappe.log_error(
                    title="AIDA Chat API Error", message=f"HTTP {resp.status_code}: {resp.text[:500]}"
                )
                fail(_friendly_error(status=resp.status_code))
                return

            finish_reason = None
            tokens = {}
            done = False
            started_at = time.monotonic()
            sent_conv = conversation_id
            new_chars = 0
            retried = False
            while True:
                retry_needed = False
                for event in _iter_events_polled(resp, session_id):
                    if is_cancelled(session_id):
                        if restricted:
                            _abort_unpersisted(emit, message_id, full_response, block_builder)
                        else:
                            _handle_stream_aborted(
                                session_id, message_id, full_response, block_builder, [], model_used, resp
                            )
                        return
                    if event is None:
                        continue
                    etype = event.get("type")
                    if etype == "start":
                        new_id = event.get("conversation_id")
                        if sent_conv and new_id and new_id != sent_conv and not new_chars and not retried:
                            # The API answered 200 but opened a NEW conversation: it has no memory.
                            retry_needed = True
                            break
                        conversation_id = new_id or conversation_id
                        if conversation_id and not restricted:
                            set_conversation_id(session_id, user, conversation_id)
                    elif etype == "chunk":
                        chunk = event.get("content") or ""
                        if chunk:
                            new_chars += len(chunk)
                            full_response += chunk
                            block_builder.add_text(chunk)
                            emit({"event": "stream_chunk", "chunk": chunk, "accumulated": full_response, "message_id": message_id})
                    elif etype == "tokens":
                        tokens = event
                        model_used = event.get("model") or model_used
                        finish_reason = event.get("finish_reason")
                    elif etype == "done":
                        conversation_id = event.get("conversation_id") or conversation_id
                        if conversation_id and not restricted:
                            set_conversation_id(session_id, user, conversation_id)
                        done = True
                        break
                    elif etype == "error":
                        frappe.log_error(title="AIDA Chat API Error", message=str(event)[:500])
                        fail(_friendly_error())
                        return
                if not retry_needed:
                    break
                resp.close()
                clear_conversation_id(session_id)
                conversation_id = None
                sent_conv = None
                retried = True
                resp = _open_stream(url, headers, make_body(None))
                if resp.status_code != 200:
                    frappe.log_error(
                        title="AIDA Chat API Error", message=f"HTTP {resp.status_code}: {resp.text[:500]}"
                    )
                    fail(_friendly_error(status=resp.status_code))
                    return

        if not new_chars or not full_response.strip():
            fail(_("AIDA returned an empty answer. Please try again."))
            return
        if not done:
            fail(_("The answer was cut off before it finished. Please try again."))
            return

        usage = {
            "prompt_tokens": int(tokens.get("prompt_tokens") or 0),
            "completion_tokens": int(tokens.get("completion_tokens") or 0),
            "duration_ms": int((time.monotonic() - started_at) * 1000),
        }

        if not restricted:
            row = _find_assistant_msg_by_message_id(session_id, message_id)
            if row and not frappe.db.get_value("PA Chat Message", row, "aborted"):
                _set_pao_message_with_retry(
                    row,
                    {
                        "content": full_response,
                        "blocks": json.dumps(block_builder.snapshot()),
                        "model": model_used or None,
                        "credits_used": 0,
                        **usage,
                        **({"tool_calls": json.dumps(tool_calls_log)} if tool_calls_log else {}),
                    },
                )

        complete = {
            "event": "stream_complete",
            "message_id": message_id,
            "full_response": full_response,
            "model_id": model_used,
            "blocks": block_builder.snapshot(),
            "quota_remaining": -1,
            "quota_used": 0,
            "quota_total": -1,
            "credits_used": 0,
            **usage,
        }
        if finish_reason == "length":
            complete["truncated"] = True
            complete["stop_reason"] = "max_tokens"
        emit(complete)

    except requests.exceptions.RequestException as e:
        frappe.log_error(title="AIDA Chat API Error", message=str(e)[:500])
        fail(_friendly_error(exc=e))
    except Exception as e:
        import traceback

        frappe.log_error(title="AIDA Stream Error", message=f"{e!s}\n{traceback.format_exc()}")
        fail(_friendly_error())
    finally:
        release_turn(session_id)
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass


def _abort_unpersisted(emit, message_id, full_response, block_builder):
    marked, blocks = append_abort_marker(full_response, block_builder.snapshot())
    emit({"event": "stream_aborted", "message_id": message_id, "partial_response": marked, "blocks": blocks})
