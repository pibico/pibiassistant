"""The only way provider code talks to the network.

Handles URL validation and pinning, bounded retries, bounded body reads, error
mapping and SSE reading. Never logs bodies or headers.
"""

import json
import queue
import random
import socket
import threading
import time

import requests
import urllib3

from . import urlsafe
from .errors import (
    ProviderCancelled,
    ProviderError,
    ProviderNetworkError,
    ProviderServerError,
    ProviderTimeoutError,
    make_error,
    scrub,
)

RETRY_STATUSES = (429, 500, 502, 503, 504, 529)
RETRY_DELAYS = (1.0, 2.0)  # module level so tests can shrink them
RETRY_AFTER_CAP = 20.0
ERROR_BODY_MAX = 64 * 1024
LINE_MAX = 1024 * 1024
MODELS_MAX = 2 * 1024 * 1024
DEFAULT_MAX_BYTES = 8 * 1024 * 1024


def map_exception(exc, row=None):
    """Translate a requests/urllib3/socket exception into a ProviderError."""
    if isinstance(exc, ProviderError):
        return exc
    kw = _ctx(row)
    if isinstance(exc, (requests.exceptions.Timeout, urllib3.exceptions.TimeoutError, socket.timeout, TimeoutError)):
        return ProviderTimeoutError(**kw)
    return ProviderNetworkError(**kw)


def _ctx(row):
    row = row or {}
    return {"provider": row.get("slug") or row.get("provider_id") or "", "label": row.get("label") or ""}


def _retry_after(headers):
    try:
        v = float(headers.get("retry-after"))
        return max(0.0, v)
    except (TypeError, ValueError):
        return None


def error_from_body(status, body, headers=None, row=None, key=None, code_hint=None):
    """Build the ProviderError for an HTTP failure or an in-stream error object."""
    headers = headers or {}
    err = body.get("error") if isinstance(body, dict) else None
    message, code = "", code_hint or ""
    if isinstance(err, dict):
        message = err.get("message") or ""
        code = str(err.get("code") or err.get("type") or code or "")
    elif isinstance(err, str):
        message = err
    elif isinstance(body, dict):
        message = body.get("message") or ""
        code = str(body.get("code") or code or "")
    message = scrub(message, key)[:300] if isinstance(message, str) else ""
    rid = headers.get("x-request-id") or headers.get("request-id") or (
        body.get("request_id") if isinstance(body, dict) else None
    )
    lowcode = code.lower()
    low = message.lower()
    if status in (None, 200):
        status = None
    if lowcode in ("insufficient_quota", "billing_error") or status == 402:
        kind = "quota"
    elif status in (401, 403) or lowcode in ("authentication_error", "permission_error", "invalid_api_key"):
        kind = "auth"
    elif status == 429 or lowcode in ("rate_limit_error", "rate_limit_exceeded"):
        kind = "rate_limit"
    elif status in (503, 529) or lowcode == "overloaded_error":
        kind = "overloaded"
    elif status == 404 or lowcode == "not_found_error":
        kind = "not_found"
    elif status in (408, 504):
        kind = "timeout"
    elif lowcode in ("content_filter", "content_policy_violation") or "responsibleaipolicyviolation" in low.replace(
        " ", ""
    ):
        kind = "content_filter"
    elif status in (400, 413, 422) or lowcode == "invalid_request_error":
        kind = "invalid_request"
    elif status is not None and 300 <= status < 400:
        kind, message = "server", "unexpected redirect"
    elif status is not None and status >= 500 or lowcode in ("api_error", "server_error"):
        kind = "server"
    elif status is not None and status >= 400:
        kind = "invalid_request"
    else:
        kind = "server"
    return make_error(
        kind,
        message,
        status=status,
        request_id=str(rid)[:100] if rid else None,
        retry_after=_retry_after(headers),
        **_ctx(row),
    )


def _read_limited(resp, limit):
    chunks, total = [], 0
    try:
        while total < limit:
            c = resp.raw.read(min(8192, limit - total), decode_content=True)
            if not c:
                break
            chunks.append(c)
            total += len(c)
    except Exception:
        pass
    return b"".join(chunks)


def _error_response(resp, row, key):
    body = _read_limited(resp, ERROR_BODY_MAX)
    try:
        data = json.loads(body.decode("utf-8", "replace"))
        if not isinstance(data, dict):
            data = {}
    except ValueError:
        data = {}
    err = error_from_body(resp.status_code, data, resp.headers, row, key)
    resp.close()
    return err


def _sleep(seconds, cancel, row):
    end = time.monotonic() + seconds
    while True:
        if cancel and cancel():
            raise ProviderCancelled(**_ctx(row))
        left = end - time.monotonic()
        if left <= 0:
            return
        time.sleep(min(0.25, left))


def request(
    adapter_row,
    method,
    url,
    *,
    headers,
    json_body=None,
    stream=False,
    timeout=(10, 120),
    key=None,
    max_bytes=DEFAULT_MAX_BYTES,
    cancel=None,
):
    """Send one logical request (up to 3 attempts). Returns a 2xx response or raises ProviderError."""
    row = adapter_row or {}
    data = None
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
    last = None
    for attempt in range(len(RETRY_DELAYS) + 1):
        if cancel and cancel():
            raise ProviderCancelled(**_ctx(row))
        # validated on every attempt: DNS may have changed since the last one
        validated = urlsafe.validate_request_url(url)
        try:
            resp = urlsafe.open_pinned(
                validated, method, url, headers=headers, stream=True, timeout=timeout, data=data
            )
        except ProviderError:
            raise
        except requests.exceptions.SSLError:
            raise ProviderNetworkError(**_ctx(row)) from None
        except requests.exceptions.ConnectTimeout:
            last = ProviderTimeoutError(**_ctx(row))
        except requests.exceptions.ConnectionError:
            last = ProviderNetworkError(**_ctx(row))
        except requests.exceptions.Timeout:
            raise ProviderTimeoutError(**_ctx(row)) from None
        except requests.exceptions.RequestException:
            raise ProviderNetworkError(**_ctx(row)) from None
        else:
            if 200 <= resp.status_code < 300:
                if stream:
                    return resp
                return _buffer(resp, max_bytes, row)
            err = _error_response(resp, row, key)
            if err.status in RETRY_STATUSES and err.kind != "quota":
                last = err
            else:
                raise err
        if attempt >= len(RETRY_DELAYS):
            break
        delay = RETRY_DELAYS[attempt] + (random.random() * 0.25 if RETRY_DELAYS[attempt] else 0)
        ra = getattr(last, "retry_after", None)
        if ra is not None:
            delay = min(ra, RETRY_AFTER_CAP)
        _sleep(delay, cancel, row)
    raise last


def _buffer(resp, max_bytes, row):
    """Read the whole body with a size cap so resp.json() is safe."""
    chunks, total = [], 0
    try:
        while True:
            c = resp.raw.read(65536, decode_content=True)
            if not c:
                break
            total += len(c)
            if total > max_bytes:
                raise ProviderServerError("response too large", **_ctx(row))
            chunks.append(c)
    except ProviderError:
        raise
    except Exception as e:
        raise map_exception(e, row) from None
    finally:
        resp.close()
    resp._content = b"".join(chunks)
    resp._content_consumed = True
    return resp


def json_of(resp, row=None):
    try:
        data = resp.json()
    except ValueError:
        raise ProviderServerError("invalid response", **_ctx(row)) from None
    if not isinstance(data, dict):
        raise ProviderServerError("invalid response", **_ctx(row))
    return data


def close_response(resp):
    """Close a streamed response without waiting for a reader blocked on the socket.

    Closing the buffered file while another thread is inside recv() would block until
    the server speaks again, so the socket is shut down first to wake that thread.
    """
    try:
        conn = getattr(resp.raw, "_connection", None)
        sock = getattr(conn, "sock", None)
        if sock is not None:
            sock.shutdown(socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        resp.close()
    except Exception:
        pass


def iter_sse(resp, cancel=None, row=None):
    """Yield (event, data) pairs; yields ("cancelled", None) when cancel() turns true.

    A reader thread feeds a queue so the caller can poll cancel() every second even
    while the socket is silent. Raises ProviderError on transport failures.
    """
    q = queue.Queue(maxsize=256)
    stop = threading.Event()

    def put(item):
        while not stop.is_set():
            try:
                q.put(item, timeout=0.5)
                return
            except queue.Full:
                continue

    def reader():
        buf = b""
        try:
            read = getattr(resp.raw, "read1", None)
            while not stop.is_set():
                chunk = read(4096, decode_content=True) if read else resp.raw.read(4096, decode_content=True)
                if not chunk:
                    break
                buf += chunk
                while True:
                    i = buf.find(b"\n")
                    if i < 0:
                        break
                    line, buf = buf[:i], buf[i + 1 :]
                    put(("line", line.rstrip(b"\r").decode("utf-8", "replace")))
                if len(buf) > LINE_MAX:
                    raise ProviderServerError("stream line too long", **_ctx(row))
            if buf:
                put(("line", buf.decode("utf-8", "replace")))
            put(("eof", None))
        except BaseException as e:  # noqa: BLE001 - forwarded to the consumer
            put(("exc", map_exception(e, row)))

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    event, data = None, []
    last_check = time.monotonic()
    try:
        while True:
            if cancel and time.monotonic() - last_check >= 1.0:
                last_check = time.monotonic()
                if cancel():
                    close_response(resp)
                    yield "cancelled", None
                    return
            try:
                kind, payload = q.get(timeout=1.0)
            except queue.Empty:
                if cancel:
                    last_check = time.monotonic()
                    if cancel():
                        close_response(resp)
                        yield "cancelled", None
                        return
                continue
            if kind == "exc":
                raise payload
            if kind == "eof":
                if data:
                    yield event, "\n".join(data)
                return
            line = payload
            if line == "":
                if data:
                    yield event, "\n".join(data)
                event, data = None, []
            elif line.startswith(":"):
                continue
            elif line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:][1:] if line[5:6] == " " else line[5:])
    finally:
        stop.set()
        close_response(resp)


def clamp_timeout(value, default=120):
    try:
        v = int(value or 0)
    except (TypeError, ValueError):
        v = 0
    if v <= 0:
        v = default
    return max(10, min(600, v))
