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
from ..chat.cancel import append_abort_marker, is_cancelled
from ..chat.helpers import _emit_socket_event, _ensure_assistant_msg, _find_assistant_msg_by_message_id

_STATE_SIG = "aida-conversation"
_TRANSCRIPT_MAX_MESSAGES = 20
_TRANSCRIPT_MAX_CHARS = 1500
# (connect, read): read bounds the gap between SSE lines, which is also how
# often the Stop flag gets a chance to be polled while the model is silent.
_TIMEOUT = (10, 90)
_TURN_LOCK_TTL = 600


def _turn_lock_key(session_id: str) -> str:
    return frappe.cache().make_key(f"pa_aida_turn:{session_id}")


def acquire_turn(session_id: str) -> bool:
    """Claim the single in-flight turn of a session (atomic; expires if the relay dies)."""
    return bool(frappe.cache().set(_turn_lock_key(session_id), "1", nx=True, ex=_TURN_LOCK_TTL))


def release_turn(session_id: str) -> None:
    try:
        frappe.cache().delete(_turn_lock_key(session_id))
    except Exception:
        pass


def is_aida_mode() -> bool:
    """True when PA Core Settings has an AIDA API key (native AIDA mode)."""
    try:
        return bool(frappe.get_doc("PA Core Settings").get_password("aida_api_key", raise_exception=False))
    except Exception:
        return False


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
    filters = {"session_id": session_id, "errored": 0, "aborted": 0}
    if exclude_name:
        filters["name"] = ["!=", exclude_name]
    rows = frappe.get_all(
        "PA Chat Message",
        filters=filters,
        fields=["role", "content"],
        order_by="creation desc",
        limit_page_length=_TRANSCRIPT_MAX_MESSAGES,
    )
    lines = []
    for r in reversed(rows):
        if not r.content:
            continue
        label = "USER" if r.role == "user" else "ASSISTANT"
        lines.append(f"{label}: {r.content[:_TRANSCRIPT_MAX_CHARS]}")
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
    block_builder = BlockBuilder()
    message_id = continue_from_message_id or uuid.uuid4().hex[:10]
    full_response = ""
    model_used = model or ""
    resp = None
    prefix = ""

    def emit(payload):
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

        if not restricted and not continue_from_message_id:
            _ensure_assistant_msg(session_id, message_id, context)
        emit({"event": "stream_start", "message_id": message_id, "model_id": model_used})

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
                conversation_id = event.get("conversation_id") or conversation_id
                if conversation_id and not restricted:
                    set_conversation_id(session_id, user, conversation_id)
            elif etype == "chunk":
                chunk = event.get("content") or ""
                if chunk:
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

        if not done and not full_response:
            fail(_friendly_error())
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
