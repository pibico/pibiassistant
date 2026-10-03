"""Anthropic Messages API adapter."""

import json

from . import http
from .base import MAX_MODELS, BaseAdapter
from .errors import ProviderCancelled, ProviderError, ProviderNetworkError, ProviderServerError
from .messages import to_anthropic, to_anthropic_tools

API_VERSION = "2023-06-01"
_FINISH = {"end_turn": "stop", "stop_sequence": "stop", "tool_use": "tool_calls", "max_tokens": "length",
           "refusal": "content_filter", "pause_turn": "stop"}


def _int(v):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


def _prompt_tokens(u):
    u = u if isinstance(u, dict) else {}
    return _int(u.get("input_tokens")) + _int(u.get("cache_read_input_tokens")) + _int(
        u.get("cache_creation_input_tokens")
    )


class AnthropicAdapter(BaseAdapter):
    def _headers(self, key, stream=False):
        h = {
            "Content-Type": "application/json",
            "anthropic-version": API_VERSION,
            "Accept": "text/event-stream" if stream else "application/json",
        }
        if stream:
            h["Accept-Encoding"] = "identity"
        if key:
            h["x-api-key"] = key
        return h

    def _prepare(self, messages, tools, model, max_tokens, stream, thinking_disabled=False):
        model = self._model(model)
        specs = to_anthropic_tools(tools)
        system, msgs = to_anthropic(messages, with_tools=bool(specs))
        body = {"model": model, "max_tokens": self._max_tokens(max_tokens, model), "messages": msgs}
        if system:
            body["system"] = system
        if specs:
            body["tools"] = specs
        if stream:
            body["stream"] = True
        if thinking_disabled:
            body["thinking"] = {"type": "disabled"}
        return model, body

    def _send(self, body, stream, cancel, key, model):
        return http.request(
            self._row_info(),
            "POST",
            self._base() + "/v1/messages",
            headers=self._headers(key, stream),
            json_body=body,
            stream=stream,
            timeout=self._timeout(model, stream),
            key=key,
            cancel=cancel,
        )

    def chat(self, messages, tools=None, model=None, max_tokens=None, cancel=None, **kw):
        key = self._need_key()
        model, body = self._prepare(
            messages, tools, model, max_tokens, False, thinking_disabled=bool(kw.get("_thinking_disabled"))
        )
        data = http.json_of(self._send(body, False, cancel, key, model), self._row_info())
        blocks = data.get("content")
        if not isinstance(blocks, list):
            raise ProviderServerError("empty response", **self._ctx())
        blocks = [b for b in blocks if isinstance(b, dict)]
        text = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
        calls = [
            {"name": str(b["name"]), "arguments": b["input"] if isinstance(b.get("input"), dict) else {}}
            for b in blocks
            if b.get("type") == "tool_use" and b.get("name")
        ]
        finish = _FINISH.get(data.get("stop_reason"), "stop")
        if calls:
            finish = "tool_calls"
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return {
            "content": text,
            "tool_calls": calls,
            "usage": {"prompt_tokens": _prompt_tokens(usage), "completion_tokens": _int(usage.get("output_tokens"))},
            "model": data.get("model") or model,
            "finish_reason": finish,
            "raw": blocks if calls else None,
        }

    def stream_chat(self, messages, tools=None, model=None, max_tokens=None, cancel=None):
        key = self._need_key()
        model, body = self._prepare(messages, tools, model, max_tokens, True)
        try:
            resp = self._send(body, True, cancel, key, model)
        except ProviderCancelled:
            yield {"type": "cancelled"}
            return
        row = self._row_info()
        prompt, completion, finish, model_out = 0, 0, None, model
        got, stopped = False, False
        try:
            for ev, data in http.iter_sse(resp, cancel, row):
                if ev == "cancelled":
                    yield {"type": "cancelled"}
                    return
                try:
                    obj = json.loads(data)
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                kind = obj.get("type") or ev
                if kind == "error":
                    raise http.error_from_body(None, obj, row=row, key=key)
                if kind == "message_start":
                    msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
                    prompt = _prompt_tokens(msg.get("usage"))
                    model_out = msg.get("model") or model_out
                elif kind == "content_block_delta":
                    delta = obj.get("delta") if isinstance(obj.get("delta"), dict) else {}
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        got = True
                        yield {"type": "chunk", "content": delta["text"]}
                elif kind == "message_delta":
                    d = obj.get("delta") if isinstance(obj.get("delta"), dict) else {}
                    if d.get("stop_reason"):
                        finish = _FINISH.get(d["stop_reason"], "stop")
                    u = obj.get("usage") if isinstance(obj.get("usage"), dict) else {}
                    completion = _int(u.get("output_tokens")) or completion
                    if u.get("input_tokens"):
                        prompt = _prompt_tokens(u) or prompt
                elif kind == "message_stop":
                    stopped = True
                    break
            if not stopped and finish is None:
                raise ProviderNetworkError(**self._ctx())
            yield {
                "type": "done",
                "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
                "model": model_out,
                "finish_reason": finish or "stop",
            }
        except ProviderError as e:
            e.provider, e.label = e.provider or self.slug, e.label or self.label
            if not got:
                raise
            yield {"type": "error", "kind": e.kind, "message": e.user_message()}
        finally:
            http.close_response(resp)

    def _list(self, limit, cancel=None, pages=1):
        key = self._need_key()
        out, after = [], None
        for _page in range(pages):
            url = f"{self._base()}/v1/models?limit={limit}" + (f"&after_id={after}" if after else "")
            resp = http.request(
                self._row_info(), "GET", url, headers=self._headers(key), timeout=(10, 30), key=key,
                max_bytes=http.MODELS_MAX, cancel=cancel,
            )
            data = http.json_of(resp, self._row_info())
            for m in data.get("data") or []:
                if isinstance(m, dict) and isinstance(m.get("id"), str) and m["id"]:
                    out.append({"id": m["id"], "label": str(m.get("display_name") or m["id"])})
            after = data.get("last_id")
            if not (data.get("has_more") and after):
                break
        return out

    def list_models(self):
        seen, out = set(), []
        for m in self._list(1000, pages=10):
            if m["id"] not in seen:
                seen.add(m["id"])
                out.append(m)
        out.sort(key=lambda m: m["id"].lower())
        return out[:MAX_MODELS]

    def _test_impl(self):
        self._list(1)
        return "", []
