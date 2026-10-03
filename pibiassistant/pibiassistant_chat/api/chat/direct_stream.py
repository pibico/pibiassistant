# pibiAssistant - Direct provider stream relay
# AGPL-3.0 License

"""Relay one chat turn answered by a direct LLM provider (OpenAI, Anthropic, ...) to the SPA.

Same contract as ``aida_stream._relay_aida_stream`` (Socket.IO events, persistence,
tool loop with approval cards) but the model is reached through a provider adapter and
the conversation memory is rebuilt from the local transcript on every turn.
"""

from __future__ import annotations

import json
import time
import uuid

import frappe
from frappe import _

from .._untrusted import wrap_untrusted
from ..chat.cancel import is_cancelled
from ..chat.helpers import _emit_socket_event, _ensure_assistant_msg, _find_assistant_msg_by_message_id
from .aida_stream import _abort_unpersisted, clear_conversation_id, refresh_turn, release_turn

_PREFIX_MATCH_CHARS = 200


def _relay_direct_stream(
    session_id,
    message,
    message_name,
    user,
    restricted=False,
    system_prompt_addendum=None,
    context=None,
    continue_from_message_id=None,
    slug="",
    model="",
    resume_responses=None,
    extract_files=False,
):
    """Stream one direct-provider turn to the SPA, persisting the assistant row unless restricted."""
    from ..block_builder import BlockBuilder
    from ..chat.relay import _handle_stream_aborted, _persist_partial_assistant_turn, _set_pao_message_with_retry
    from ..llm_config import provider_by_slug
    from .aida_tools import (
        _history_messages,
        _system_prompt,
        chat_tool_specs,
        chunk_text,
        resume_tool_turn,
        run_tool_turn,
        tools_enabled,
    )
    from .providers import get_provider
    from .providers.errors import ProviderCancelled, ProviderError, log_provider_error

    try:
        import frappe.translate

        frappe.local.lang = frappe.translate.get_user_lang(user)
    except Exception:
        pass
    block_builder = BlockBuilder()
    message_id = continue_from_message_id or uuid.uuid4().hex[:10]
    full_response = ""
    model_used = f"{slug}/{model}" if slug and model else (model or "")
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
        row = provider_by_slug(slug)
        if not row:
            fail(_("This AI provider is no longer available. Pick another model."))
            return

        if continue_from_message_id and not restricted:
            msg_row = frappe.db.get_value(
                "PA Chat Message",
                {"session_id": session_id, "role": "assistant", "message_id": continue_from_message_id},
                ["content", "blocks"],
                as_dict=True,
            )
            if msg_row and msg_row.blocks:
                try:
                    block_builder = BlockBuilder(existing_blocks=json.loads(msg_row.blocks))
                except ValueError:
                    pass
            prefix = (msg_row.content if msg_row else "") or ""
            full_response = prefix

        user_text = message or ""
        if system_prompt_addendum:
            user_text = f"{system_prompt_addendum}\n\n{user_text}"

        emit(
            {
                "event": "stream_start",
                "message_id": message_id,
                "model_id": model_used,
                **({"resumed": True} if resume_responses is not None else {}),
            }
        )

        if extract_files and message_name and not restricted:
            from .helpers import _extract_file_attachments

            file_content = _extract_file_attachments(message_name, parallel=True)
            if file_content:
                system_prompt_addendum = (system_prompt_addendum or "") + wrap_untrusted(
                    file_content, kind="user_attached_files"
                )
                user_text = f"{system_prompt_addendum}\n\n{message or ''}"

        continuing = bool(continue_from_message_id) and not restricted
        messages = [{"role": "system", "content": _system_prompt(user)}]
        if not restricted:
            history = _history_messages(session_id, None if continuing else message_name)
        else:
            history = []
        if continuing:
            if history and history[-1]["role"] == "assistant" and prefix.startswith(
                history[-1]["content"][:_PREFIX_MATCH_CHARS]
            ):
                history.pop()
            messages += history
            if prefix.strip():
                messages.append({"role": "assistant", "content": prefix})
            messages.append({"role": "user", "content": _("Continue your previous answer exactly where it stopped.")})
        else:
            messages += history
            messages.append({"role": "user", "content": user_text})

        finish_reason = None
        tokens = {}
        done = False
        started_at = time.monotonic()
        new_chars = 0
        tool_calls_log = []
        tool_done = False

        resuming = resume_responses is not None
        outcome = None
        backend = {"kind": "direct", "slug": slug}
        if tools_enabled() and row.get("supports_tools") and (resuming or not continue_from_message_id):
            try:
                specs = chat_tool_specs(user)
                if resuming:
                    block_builder.resolve_pending_interactions(resume_responses)
                    outcome = resume_tool_turn(
                        session_id=session_id,
                        user=user,
                        responses=resume_responses,
                        api_url="",
                        api_key="",
                        specs=specs,
                        emit=emit,
                        block_builder=block_builder,
                        backend=backend,
                    )
                elif specs:
                    outcome = run_tool_turn(
                        session_id=session_id,
                        user=user,
                        message=user_text,
                        message_name=message_name,
                        message_id=message_id,
                        api_url="",
                        api_key="",
                        provider=slug,
                        model=model,
                        specs=specs,
                        emit=emit,
                        block_builder=block_builder,
                        backend=backend,
                    )
            except ProviderCancelled:
                outcome = {"aborted": True}
            except Exception as e:
                if isinstance(e, ProviderError):
                    log_provider_error(e)
                    message_out = e.user_message()
                else:
                    frappe.log_error(title="LLM Tool Turn Error", message=type(e).__name__)
                    message_out = _("The assistant could not answer right now. Please try again.")
                # Once a tool has run its result is only in this turn: a plain re-run would answer blind
                # (or repeat a change), so surface the failure instead.
                if resuming or block_builder.snapshot() or isinstance(e, ProviderError):
                    fail(message_out)
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
                text_out = ("\n\n" + outcome["text"]) if prefix.strip() and not new_chars else outcome["text"]
                for piece in chunk_text(text_out):
                    full_response += piece
                    new_chars += len(piece)
                    block_builder.add_text(piece)
                    emit({"event": "stream_chunk", "chunk": piece, "accumulated": full_response, "message_id": message_id})
            if outcome and (outcome.get("text") or outcome.get("interrupted")):
                model_used = f"{slug}/{outcome['model']}" if outcome.get("model") else model_used
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
                    msg_name = _find_assistant_msg_by_message_id(session_id, message_id)
                    if msg_name:
                        _set_pao_message_with_retry(
                            msg_name,
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
            fail(_("The assistant returned an empty answer. Please try again."))
            return

        if not tool_done:
            adapter = get_provider(row)
            gen = adapter.stream_chat(messages, model=model, cancel=lambda: is_cancelled(session_id))
            started_at = time.monotonic()
            try:
                for event in gen:
                    if is_cancelled(session_id):
                        if restricted:
                            _abort_unpersisted(emit, message_id, full_response, block_builder)
                        else:
                            _handle_stream_aborted(
                                session_id, message_id, full_response, block_builder, [], model_used, gen
                            )
                        return
                    etype = event.get("type")
                    if etype == "chunk":
                        chunk = event.get("content") or ""
                        if chunk:
                            new_chars += len(chunk)
                            full_response += chunk
                            block_builder.add_text(chunk)
                            emit(
                                {
                                    "event": "stream_chunk",
                                    "chunk": chunk,
                                    "accumulated": full_response,
                                    "message_id": message_id,
                                }
                            )
                    elif etype == "cancelled":
                        if restricted:
                            _abort_unpersisted(emit, message_id, full_response, block_builder)
                        else:
                            _handle_stream_aborted(
                                session_id, message_id, full_response, block_builder, [], model_used, gen
                            )
                        return
                    elif etype == "error":
                        fail(event.get("message") or _("The assistant could not answer right now. Please try again."))
                        return
                    elif etype == "done":
                        tokens = event.get("usage") or {}
                        finish_reason = event.get("finish_reason")
                        if event.get("model"):
                            model_used = f"{slug}/{event['model']}"
                        done = True
                        break
            finally:
                try:
                    gen.close()
                except Exception:
                    pass

        if not new_chars or not full_response.strip():
            fail(_("The assistant returned an empty answer. Please try again."))
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
            msg_name = _find_assistant_msg_by_message_id(session_id, message_id)
            if msg_name and not frappe.db.get_value("PA Chat Message", msg_name, "aborted"):
                _set_pao_message_with_retry(
                    msg_name,
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
        # AIDA keeps its own memory; a later AIDA turn must rebuild it from the transcript.
        clear_conversation_id(session_id)

    except ProviderCancelled:
        if restricted:
            _abort_unpersisted(emit, message_id, full_response, block_builder)
        else:
            _handle_stream_aborted(session_id, message_id, full_response, block_builder, [], model_used, None)
    except ProviderError as e:
        log_provider_error(e)
        fail(e.user_message())
    except Exception as e:
        frappe.log_error(title="LLM Stream Error", message=f"{type(e).__name__}\n{frappe.get_traceback()[-1500:]}")
        fail(_("The assistant could not answer right now. Please try again."))
    finally:
        release_turn(session_id)
