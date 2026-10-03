"""OpenAI chat-completions family: OpenAI, DeepSeek, Qwen, xAI, Azure OpenAI and generic servers."""

import json
import re
from urllib.parse import quote

from frappe import _

from . import http
from .base import MAX_MODELS, BaseAdapter
from .errors import (
    ProviderCancelled,
    ProviderConfigError,
    ProviderContentFilterError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderNetworkError,
    ProviderNotFoundError,
    ProviderServerError,
    ProviderUnsupportedError,
)
from .messages import to_openai_messages, to_openai_tools
from .registry import filter_models

REASONING_RE = re.compile(r"^(o\d|gpt-5)")
_GPT5_N = re.compile(r"^gpt-5\.(\d+)")
_THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.S)
_THINK_OPEN = re.compile(r"<think>.*$", re.S)
_DEPLOYMENT = re.compile(r"^(?!\.)[A-Za-z0-9._-]{1,64}$")
_FINISH = {"stop": "stop", "length": "length", "tool_calls": "tool_calls", "function_call": "tool_calls",
           "content_filter": "content_filter"}


def _args(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            v = json.loads(value)
        except ValueError:
            return {}
        return v if isinstance(v, dict) else {}
    return {}


def _content_text(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict) and isinstance(p.get("text"), str):
                parts.append(p["text"])
        return "".join(parts)
    return ""


def _int(v):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


def _usage(u):
    u = u if isinstance(u, dict) else {}
    return {"prompt_tokens": _int(u.get("prompt_tokens")), "completion_tokens": _int(u.get("completion_tokens"))}


def _parse_tool_calls(msg):
    out = []
    for tc in msg.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
        if fn.get("name"):
            out.append({"name": str(fn["name"]), "arguments": _args(fn.get("arguments"))})
    fc = msg.get("function_call")
    if not out and isinstance(fc, dict) and fc.get("name"):
        out.append({"name": str(fc["name"]), "arguments": _args(fc.get("arguments"))})
    return out


class ThinkStripper:
    """Removes inline <think>...</think> from a stream split at arbitrary points."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self):
        self.inside = False
        self.buf = ""
        self._lstrip = False

    def feed(self, text, final=False):
        self.buf += text
        out = []
        while True:
            if self.inside:
                i = self.buf.find(self.CLOSE)
                if i < 0:
                    self.buf = "" if final else self.buf[-(len(self.CLOSE) - 1):]
                    break
                self.buf = self.buf[i + len(self.CLOSE):]
                self.inside = False
                self._lstrip = True
                continue
            i = self.buf.find(self.OPEN)
            if i >= 0:
                out.append(self.buf[:i])
                self.buf = self.buf[i + len(self.OPEN):]
                self.inside = True
                continue
            hold = 0
            if not final:
                for k in range(min(len(self.OPEN) - 1, len(self.buf)), 0, -1):
                    if self.OPEN.startswith(self.buf[-k:]):
                        hold = k
                        break
            out.append(self.buf[: len(self.buf) - hold])
            self.buf = self.buf[len(self.buf) - hold:]
            break
        text = "".join(out)
        if self._lstrip and text:
            text = text.lstrip()
            self._lstrip = not text
        return text


class OpenAICompatAdapter(BaseAdapter):
    STRIP_THINK = False
    MAP_TOOLS_UNSUPPORTED = False
    REASONING_LENGTH_ERROR = False

    # -- request building -------------------------------------------------
    def _url(self, model):
        return self._base() + "/chat/completions"

    def _headers(self, key, stream):
        h = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        }
        if stream:
            h["Accept-Encoding"] = "identity"
        if key:
            h["Authorization"] = f"Bearer {key}"
        return h

    def _token_param(self, model):
        return "max_tokens"

    def _tune(self, body, model, has_tools):
        pass

    def _prepare(self, messages, tools, model, max_tokens, stream):
        model = self._model(model)
        body = {"model": model, "messages": to_openai_messages(messages)}
        specs = to_openai_tools(tools)
        if specs:
            body["tools"] = specs
        body[self._token_param(model)] = self._max_tokens(max_tokens, model)
        if stream:
            body["stream"] = True
            body["stream_options"] = {"include_usage": True}
        self._tune(body, model, bool(specs))
        return model, body

    def _adapt(self, body, err, tried):
        """Fix the request after a 400 that names a parameter. True when the body changed."""
        text = (err.safe_message or "").lower()
        if not text:
            return False
        for a, b in (("max_tokens", "max_completion_tokens"), ("max_completion_tokens", "max_tokens")):
            if a in text and a in body and ("swap", a) not in tried:
                tried.add(("swap", a))
                body[b] = body.pop(a)
                return True
        if (
            ("reasoning_effort" in text or "reasoning effort" in text)
            and ("tool" in text or "function" in text)
            and body.get("reasoning_effort") != "none"
            and "re" not in tried
        ):
            tried.add("re")
            body["reasoning_effort"] = "none"
            return True
        if "stream_options" in text and "stream_options" in body and "so" not in tried:
            tried.add("so")
            body.pop("stream_options")
            return True
        return False

    def _send(self, body, model, stream, cancel, key):
        tried = set()
        while True:
            try:
                return http.request(
                    self._row_info(),
                    "POST",
                    self._url(model),
                    headers=self._headers(key, stream),
                    json_body=body,
                    stream=stream,
                    timeout=self._timeout(model, stream),
                    key=key,
                    cancel=cancel,
                )
            except ProviderInvalidRequestError as e:
                if self._adapt(body, e, tried):
                    continue
                low = (e.safe_message or "").lower()
                if self.MAP_TOOLS_UNSUPPORTED and body.get("tools") and ("tool" in low or "function" in low):
                    raise ProviderUnsupportedError(e.safe_message, feature="tools", **self._ctx()) from None
                raise

    def _clean(self, text):
        if self.STRIP_THINK:
            text = _THINK_OPEN.sub("", _THINK_BLOCK.sub("", text))
        return text

    # -- chat --------------------------------------------------------------
    def chat(self, messages, tools=None, model=None, max_tokens=None, cancel=None, **_ignored):
        key = self._need_key()
        model, body = self._prepare(messages, tools, model, max_tokens, False)
        resp = self._send(body, model, False, cancel, key)
        data = http.json_of(resp, self._row_info())
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            if isinstance(data.get("error"), (dict, str)):
                raise http.error_from_body(None, data, row=self._row_info(), key=key)
            raise ProviderServerError("empty response", **self._ctx())
        choice = choices[0]
        msg = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = self._clean(_content_text(msg.get("content")))
        calls = _parse_tool_calls(msg)
        finish = _FINISH.get(choice.get("finish_reason"), "stop")
        if calls and finish != "content_filter":
            finish = "tool_calls"
        self._check_empty(content, calls, finish)
        return {
            "content": content,
            "tool_calls": calls,
            "usage": _usage(data.get("usage")),
            "model": data.get("model") or model,
            "finish_reason": finish,
            "raw": None,
        }

    def _check_empty(self, content, calls, finish):
        if content or calls:
            return
        if finish == "length" and self.REASONING_LENGTH_ERROR:
            raise ProviderInvalidRequestError(
                _("Output budget used by reasoning; raise Max output tokens"), **self._ctx()
            )
        if finish == "content_filter":
            raise ProviderContentFilterError(**self._ctx())

    # -- streaming ---------------------------------------------------------
    def stream_chat(self, messages, tools=None, model=None, max_tokens=None, cancel=None):
        key = self._need_key()
        model, body = self._prepare(messages, tools, model, max_tokens, True)
        try:
            resp = self._send(body, model, True, cancel, key)
        except ProviderCancelled:
            yield {"type": "cancelled"}
            return
        row = self._row_info()
        strip = ThinkStripper() if self.STRIP_THINK else None
        usage, finish, model_out, got, done = _usage(None), None, model, False, False
        frags = {}
        try:
            for ev, data in http.iter_sse(resp, cancel, row):
                if ev == "cancelled":
                    yield {"type": "cancelled"}
                    return
                if data.strip() == "[DONE]":
                    done = True
                    break
                try:
                    obj = json.loads(data)
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                if isinstance(obj.get("error"), (dict, str)) and not obj.get("choices"):
                    raise http.error_from_body(None, obj, row=row, key=key)
                if isinstance(obj.get("usage"), dict):
                    usage = _usage(obj["usage"])
                model_out = obj.get("model") or model_out
                choices = obj.get("choices")
                if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                    continue
                choice = choices[0]
                delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
                text = _content_text(delta.get("content"))
                if strip:
                    text = strip.feed(text)
                if text:
                    got = True
                    yield {"type": "chunk", "content": text}
                for tc in delta.get("tool_calls") or []:
                    if isinstance(tc, dict):
                        f = frags.setdefault(tc.get("index", len(frags)), {"name": "", "args": ""})
                        fn = tc.get("function") or {}
                        f["name"] += fn.get("name") or ""
                        a = fn.get("arguments")
                        f["args"] += a if isinstance(a, str) else (json.dumps(a) if a else "")
                if choice.get("finish_reason"):
                    finish = _FINISH.get(choice["finish_reason"], "stop")
            if strip:
                tail = strip.feed("", final=True)
                if tail:
                    got = True
                    yield {"type": "chunk", "content": tail}
            if not done and finish is None:
                raise ProviderNetworkError(**self._ctx())
            calls = [
                {"name": f["name"], "arguments": _args(f["args"])}
                for _i, f in sorted(frags.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 0)
                if f["name"]
            ]
            if finish is None:
                finish = "stop"
            if calls and finish != "content_filter":
                finish = "tool_calls"
            if not got and not calls:
                self._check_empty("", calls, finish)
            ev = {"type": "done", "usage": usage, "model": model_out, "finish_reason": finish}
            if calls:
                ev["tool_calls"] = calls
            yield ev
        except ProviderError as e:
            e.provider, e.label = e.provider or self.slug, e.label or self.label
            if not got:
                raise
            yield {"type": "error", "kind": e.kind, "message": e.user_message()}
        finally:
            http.close_response(resp)

    # -- models ------------------------------------------------------------
    def _models_paths(self):
        return [self.defn.models_path]

    def list_models(self):
        key = self._need_key()
        paths = self._models_paths()
        data = None
        for n, path in enumerate(paths):
            try:
                resp = http.request(
                    self._row_info(),
                    "GET",
                    self._base() + path,
                    headers=self._headers(key, False),
                    timeout=(10, 30),
                    key=key,
                    max_bytes=http.MODELS_MAX,
                )
            except ProviderNotFoundError:
                if n == len(paths) - 1:
                    raise
                continue
            data = http.json_of(resp, self._row_info())
            break
        items = data.get("data") if isinstance(data.get("data"), list) else data.get("models")
        entries = []
        for it in items if isinstance(items, list) else []:
            if isinstance(it, str):
                it = {"id": it}
            if isinstance(it, dict):
                mid = it.get("id") or it.get("name") or it.get("model")
                if isinstance(mid, str) and mid:
                    e = {"id": mid}
                    if "architecture" in it:
                        e["architecture"] = it["architecture"]
                    entries.append(e)
        out, seen = [], set()
        for e in filter_models(self.defn, entries):
            if e["id"] not in seen:
                seen.add(e["id"])
                out.append({"id": e["id"], "label": e["id"]})
        out.sort(key=lambda m: m["id"].lower())
        return out[:MAX_MODELS]


class OpenAIAdapter(OpenAICompatAdapter):
    REASONING_LENGTH_ERROR = True

    def _is_reasoning(self, model):
        return bool(REASONING_RE.match(model or ""))

    def _token_param(self, model):
        return "max_completion_tokens" if self._is_reasoning(model) else "max_tokens"

    def _tune(self, body, model, has_tools):
        m = _GPT5_N.match(model)
        if has_tools and m and int(m.group(1)) >= 4:
            body["reasoning_effort"] = "none"


class DeepSeekAdapter(OpenAICompatAdapter):
    def _tune(self, body, model, has_tools):
        body["thinking"] = {"type": "disabled"}


class QwenAdapter(OpenAICompatAdapter):
    def _tune(self, body, model, has_tools):
        body["enable_thinking"] = False


class XAIAdapter(OpenAICompatAdapter):
    def _models_paths(self):
        return ["/language-models", "/models"]


class GenericAdapter(OpenAICompatAdapter):
    STRIP_THINK = True
    MAP_TOOLS_UNSUPPORTED = True


class AzureOpenAIAdapter(OpenAICompatAdapter):
    REASONING_LENGTH_ERROR = True

    def _is_reasoning(self, model):
        return bool(REASONING_RE.match(model or ""))

    def _model(self, model):
        model = (model or self.row.get("deployment") or self.row.get("default_model") or "").strip()
        if not model:
            raise ProviderConfigError(_("Enter the deployment name"), **self._ctx())
        if not _DEPLOYMENT.match(model):
            raise ProviderConfigError(_("Enter the deployment name"), **self._ctx())
        return model

    def _token_param(self, model):
        return "max_completion_tokens"

    def _url(self, model):
        version = (self.row.get("api_version") or "2024-10-21").strip()
        return (
            f"{self._base()}/openai/deployments/{quote(model, safe='')}/chat/completions"
            f"?api-version={quote(version, safe='')}"
        )

    def _headers(self, key, stream):
        h = super()._headers(key, stream)
        h.pop("Authorization", None)
        if key:
            h["api-key"] = key
        return h

    def _prepare(self, messages, tools, model, max_tokens, stream):
        model, body = super()._prepare(messages, tools, model, max_tokens, stream)
        body.pop("model", None)
        return model, body

    def list_models(self):
        out, seen = [], set()
        names = [self.row.get("deployment"), self.row.get("default_model")] + list(self.row.get("extra_models") or [])
        for n in names:
            n = (n or "").strip()
            if n and n not in seen:
                seen.add(n)
                out.append({"id": n, "label": n})
        return out

    def _test_impl(self):
        model = self._model(None)
        self.chat(
            [{"role": "user", "content": "Reply with OK"}],
            model=model,
            max_tokens=512 if self._is_reasoning(model) else 16,
        )
        return f" - {len(self.list_models())} models", self.list_models()
