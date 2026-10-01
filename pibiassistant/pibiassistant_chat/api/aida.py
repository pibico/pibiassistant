import json
import os
import time

import frappe
import requests
from frappe import _

from ._rate_limits import rate_limit, session_user_or_ip

_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".oga", ".webm", ".mp4", ".flac", ".aac", ".opus"}
_AUDIO_MAX_BYTES = 25 * 1024 * 1024


def _get_settings():
    """Return the PA Core Settings singleton (cached per request)."""
    return frappe.get_doc("PA Core Settings")


def _get_aida_config():
    """Return AIDA Chat API URL and key from PA Core Settings."""
    settings = _get_settings()
    url = settings.aida_api_url or ""
    key = settings.get_password("aida_api_key") or ""
    provider = settings.aida_default_provider or ""
    model = settings.aida_default_model or ""
    return url.rstrip("/"), key, provider, model


def _get_convert_config():
    """Return AIDA Convert API URL and key."""
    settings = _get_settings()
    url = (settings.aida_convert_url or "").rstrip("/")
    key = settings.get_password("aida_convert_api_key") or ""
    return url, key


def _get_voice_config():
    """Return AIDA Voice API URL and key."""
    settings = _get_settings()
    url = (settings.aida_voice_url or "").rstrip("/")
    key = settings.get_password("aida_voice_api_key") or ""
    return url, key


def _emit(session_id, event, **kwargs):
    """Emit a pao_message_stream event via Socket.IO."""
    payload = {"session_id": session_id, "event": event}
    payload.update(kwargs)
    frappe.publish_realtime(
        "pao_message_stream",
        payload,
        task_id=session_id,
    )


@frappe.whitelist()
def get_models():
    """Fetch available providers and models from the AIDA Chat API."""
    api_url, api_key, _, _ = _get_aida_config()
    if not api_url or not api_key:
        return {"success": False, "providers": {}}

    try:
        r = requests.get(
            f"{api_url}/api/v1/models",
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
        return {"success": False, "providers": {}, "error": r.text[:200]}
    except Exception as e:
        return {"success": False, "providers": {}, "error": str(e)[:200]}


@frappe.whitelist()
def get_overview():
    """Non-secret AIDA configuration summary for the admin page."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    chat_url, chat_key, provider, model = _get_aida_config()
    conv_url, conv_key = _get_convert_config()
    voice_url, voice_key = _get_voice_config()
    return {
        "provider": provider,
        "model": model,
        "services": {
            "Chat": {"url": chat_url, "configured": bool(chat_url and chat_key)},
            "Convert": {"url": conv_url, "configured": bool(conv_url and conv_key)},
            "Voice": {"url": voice_url, "configured": bool(voice_url and voice_key)},
        },
    }


@frappe.whitelist()
def test_connections():
    """Test connectivity to all configured AIDA APIs. Returns status for each."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    results = {}

    # Test Chat API
    chat_url, chat_key, _p, _m = _get_aida_config()
    if chat_url and chat_key:
        try:
            r = requests.get(f"{chat_url}/api/v1/health", headers={"X-API-Key": chat_key}, timeout=10)
            results["Chat API"] = {"ok": r.status_code == 200,
                                   "detail": f"{chat_url} — HTTP {r.status_code}",
                                   "error": r.text[:100] if r.status_code != 200 else ""}
        except Exception as e:
            results["Chat API"] = {"ok": False, "error": str(e)[:100]}
    else:
        results["Chat API"] = {"ok": False, "error": _("Not configured")}

    # Test Convert API
    conv_url, conv_key = _get_convert_config()
    if conv_url and conv_key:
        try:
            r = requests.get(f"{conv_url}/api/v1/health", headers={"X-API-Key": conv_key}, timeout=10)
            results["Convert API"] = {"ok": r.status_code == 200,
                                      "detail": f"{conv_url} — HTTP {r.status_code}",
                                      "error": r.text[:100] if r.status_code != 200 else ""}
        except Exception as e:
            results["Convert API"] = {"ok": False, "error": str(e)[:100]}
    else:
        results["Convert API"] = {"ok": False, "error": _("Not configured")}

    # Test Voice API
    voice_url, voice_key = _get_voice_config()
    if voice_url and voice_key:
        try:
            r = requests.get(f"{voice_url}/api/v1/health", headers={"X-API-Key": voice_key}, timeout=10)
            results["Voice API"] = {"ok": r.status_code == 200,
                                    "detail": f"{voice_url} — HTTP {r.status_code}",
                                    "error": r.text[:100] if r.status_code != 200 else ""}
        except Exception as e:
            results["Voice API"] = {"ok": False, "error": str(e)[:100]}
    else:
        results["Voice API"] = {"ok": False, "error": _("Not configured")}

    return results


_MAX_MESSAGE_CHARS = 20000
_MAX_STREAM_SECONDS = 240


def _assert_can_use_aida():
    from .settings import can_use_pao

    check = can_use_pao()
    if not check.get("can_use"):
        frappe.throw(check.get("reason") or _("Cannot use AIDA"), frappe.PermissionError)


@frappe.whitelist()
@rate_limit(session_user_or_ip, limit=30, seconds=60)
def send_message(session_id=None, message=None, **kwargs):
    """Proxy a chat message to the AIDA API and stream the response back via Socket.IO."""
    from .chat.aida_stream import acquire_turn_waiting, release_turn

    _assert_can_use_aida()
    if message and len(message) > _MAX_MESSAGE_CHARS:
        frappe.throw(_("The message is too long."), frappe.ValidationError)
    if session_id and not frappe.utils.cstr(session_id).replace("_", "").replace("-", "").isalnum():
        frappe.throw(_("Invalid session"), frappe.ValidationError)

    locked = bool(session_id)
    if locked and not acquire_turn_waiting(session_id):
        frappe.throw(
            _("AIDA is still answering the previous message. Wait for it to finish."),
            frappe.ValidationError,
        )
    try:
        return _send_message_impl(session_id=session_id, message=message, **kwargs)
    finally:
        if locked:
            release_turn(session_id)


def _send_message_impl(session_id=None, message=None, **kwargs):
    if not message:
        frappe.throw(_("Message is required"))

    api_url, api_key, provider, model = _get_aida_config()
    if not api_url or not api_key:
        frappe.throw(_("AIDA Chat API is not configured. Go to PA Core Settings > AIDA Chat."))

    if not session_id:
        session_id = frappe.generate_hash(length=16)

    _emit(session_id, "stream_start", message_id=frappe.generate_hash(length=10))

    file_urls = frappe.parse_json(kwargs.get("file_urls") or "[]")
    if file_urls:
        from pibiassistant.plugins.data_science.tools.extract_file_content import ExtractFileContent

        from ._untrusted import wrap_untrusted

        extractor = ExtractFileContent()
        owned = {
            f.file_url: f.file_name
            for f in frappe.get_all(
                "File",
                filters={"file_url": ["in", list(file_urls)], "owner": frappe.session.user},
                fields=["file_url", "file_name"],
                limit_page_length=0,
            )
        }
        parts = []
        for url in file_urls:
            if url not in owned:
                continue
            result = extractor.execute({"file_url": url, "operation": "extract"})
            name = owned[url] or url.split("/")[-1]
            if result.get("success") and result.get("content"):
                parts.append(f"[Archivo adjunto: {name}]\n{result['content']}")
            else:
                parts.append(f"[Archivo adjunto: {name}] No se pudo extraer el contenido: {result.get('error', 'desconocido')}")
        if parts:
            message = wrap_untrusted("\n\n".join(parts), kind="user_attached_files") + "\n\n" + message

    endpoint = f"{api_url}/api/v1/chat/completions"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    body = {
        "message": message,
        "stream": True,
    }
    if provider:
        body["provider"] = provider
    if model:
        body["model"] = model

    conversation_id = kwargs.get("conversation_id")
    if conversation_id:
        body["conversation_id"] = conversation_id

    full_response = ""
    usage = {}
    started_at = time.monotonic()

    try:
        with requests.post(endpoint, json=body, headers=headers, stream=True, timeout=120) as resp:
            if resp.status_code != 200:
                error_text = resp.text[:200]
                _emit(session_id, "stream_error", error=_("AIDA API error {0}: {1}").format(resp.status_code, error_text))
                return {"ok": False, "error": error_text}

            for line in resp.iter_lines(decode_unicode=True):
                if time.monotonic() - started_at > _MAX_STREAM_SECONDS:
                    raise requests.exceptions.Timeout()
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_str)
                        content = ""
                        if chunk_data.get("type") == "tokens":
                            usage["model_id"] = chunk_data.get("model")
                            usage["prompt_tokens"] = chunk_data.get("prompt_tokens")
                            usage["completion_tokens"] = chunk_data.get("completion_tokens")
                            usage["tokens_used"] = chunk_data.get("total_tokens")
                        elif chunk_data.get("conversation_id"):
                            usage["conversation_id"] = chunk_data["conversation_id"]
                        if "choices" in chunk_data:
                            delta = chunk_data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                        elif "content" in chunk_data:
                            content = chunk_data["content"]
                        elif "chunk" in chunk_data:
                            content = chunk_data["chunk"]
                        elif "text" in chunk_data:
                            content = chunk_data["text"]

                        if content:
                            full_response += content
                            _emit(session_id, "stream_chunk", chunk=content)
                    except json.JSONDecodeError:
                        pass

        _emit(
            session_id,
            "stream_complete",
            full_response=full_response,
            tokens_used=usage.pop("tokens_used", None) or 0,
            duration_ms=int((time.monotonic() - started_at) * 1000),
            **usage,
        )
        return {"ok": True, "session_id": session_id}

    except requests.exceptions.Timeout:
        _emit(session_id, "stream_error", error=_("AIDA API request timed out"))
        return {"ok": False, "error": "timeout"}
    except requests.exceptions.ConnectionError:
        _emit(session_id, "stream_error", error=_("Cannot connect to AIDA API"))
        return {"ok": False, "error": "connection_error"}
    except Exception as e:
        _emit(session_id, "stream_error", error=str(e)[:200])
        return {"ok": False, "error": str(e)[:200]}


def convert_bytes_to_markdown(content, filename):
    """Send file bytes to the AIDA Convert API. Returns (markdown, error)."""
    convert_url, convert_key = _get_convert_config()
    if not convert_url or not convert_key:
        return "", _("AIDA Convert API is not configured")
    try:
        resp = requests.post(
            f"{convert_url}/api/v1/convert",
            headers={"X-API-Key": convert_key},
            files={"file": (filename, content)},
            data={"output_format": "markdown", "use_vlm": "true", "detect_tables": "true"},
            timeout=300,
        )
    except requests.exceptions.RequestException as e:
        return "", _("Convert API unreachable: {0}").format(str(e)[:150])
    if resp.status_code not in (200, 201):
        return "", _("Convert API error {0}: {1}").format(resp.status_code, resp.text[:200])
    result = resp.json()
    if result.get("success") is False:
        return "", _("Convert API: {0}").format(result.get("error") or _("conversion failed"))
    return result.get("markdown") or result.get("content") or "", ""


@frappe.whitelist()
def convert_document(file_url=None):
    """Convert a PDF/image/office file to markdown via the AIDA Convert API."""
    if not file_url:
        frappe.throw(_("file_url is required"))

    file_doc = frappe.get_doc("File", {"file_url": file_url})
    file_doc.check_permission("read")
    with open(file_doc.get_full_path(), "rb") as f:
        content = f.read()

    filename = file_doc.file_name or file_url.split("/")[-1]
    markdown, error = convert_bytes_to_markdown(content, filename)
    if error:
        return {"ok": False, "error": error}
    return {"ok": True, "markdown": markdown, "filename": filename}


@frappe.whitelist()
def transcribe_audio(file_url=None):
    """Transcribe an audio file via the AIDA Voice API.

    Accepts a Frappe file URL, downloads it server-side, sends it to Whisper,
    and returns the transcription text.
    """
    if not file_url:
        frappe.throw(_("file_url is required"))

    voice_url, voice_key = _get_voice_config()
    if not voice_url or not voice_key:
        frappe.throw(_("AIDA Voice API is not configured. Go to PA Core Settings > AIDA Chat."))

    roles = frappe.get_roles(frappe.session.user)
    if not {"PA User", "PA Admin", "System Manager"} & set(roles):
        frappe.throw(_("You do not have permission to use AIDA."), frappe.PermissionError)

    file_doc = frappe.get_doc("File", {"file_url": file_url})
    file_doc.check_permission("read")
    filename = file_doc.file_name or file_url.split("/")[-1]
    if os.path.splitext(filename)[1].lower() not in _AUDIO_EXTENSIONS:
        frappe.throw(_("Unsupported audio file type."))
    file_path = file_doc.get_full_path()
    if os.path.getsize(file_path) > _AUDIO_MAX_BYTES:
        frappe.throw(_("The audio file is too large."))
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{voice_url}/api/v1/transcriptions",
            headers={"X-API-Key": voice_key},
            files={"audio_file": (filename, f)},
            data={"language": "es", "task": "transcribe"},
            timeout=120,
        )

    if resp.status_code not in (200, 201):
        return {"ok": False, "error": _("Voice API error {0}: {1}").format(resp.status_code, resp.text[:200])}

    result = resp.json()
    text = result.get("text", result.get("transcription", ""))
    return {"ok": True, "text": text, "filename": filename}
