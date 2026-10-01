import json
import frappe
import requests
from frappe import _


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
def test_connections():
    """Test connectivity to all configured AIDA APIs. Returns status for each."""
    results = {}

    # Test Chat API
    chat_url, chat_key, _, _ = _get_aida_config()
    if chat_url and chat_key:
        try:
            r = requests.get(f"{chat_url}/api/v1/health", headers={"X-API-Key": chat_key}, timeout=10)
            results["Chat API"] = {"ok": r.status_code == 200,
                                   "detail": f"{chat_url} — HTTP {r.status_code}",
                                   "error": r.text[:100] if r.status_code != 200 else ""}
        except Exception as e:
            results["Chat API"] = {"ok": False, "error": str(e)[:100]}
    else:
        results["Chat API"] = {"ok": False, "error": "Not configured"}

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
        results["Convert API"] = {"ok": False, "error": "Not configured"}

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
        results["Voice API"] = {"ok": False, "error": "Not configured"}

    return results


@frappe.whitelist()
def send_message(session_id=None, message=None, **kwargs):
    """Proxy a chat message to the AIDA API and stream the response back via Socket.IO."""
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

        extractor = ExtractFileContent()
        parts = []
        for url in file_urls:
            result = extractor.execute({"file_url": url, "operation": "extract"})
            name = url.split("/")[-1]
            if result.get("success") and result.get("content"):
                parts.append(f"[Archivo adjunto: {name}]\n{result['content']}")
            else:
                parts.append(f"[Archivo adjunto: {name}] No se pudo extraer el contenido: {result.get('error', 'desconocido')}")
        message = "\n\n".join(parts) + "\n\n" + message

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

    try:
        with requests.post(endpoint, json=body, headers=headers, stream=True, timeout=120) as resp:
            if resp.status_code != 200:
                error_text = resp.text[:200]
                _emit(session_id, "stream_error", error=f"AIDA API error {resp.status_code}: {error_text}")
                return {"ok": False, "error": error_text}

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_str)
                        content = ""
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

        _emit(session_id, "stream_complete", full_response=full_response, tokens_used=0)
        return {"ok": True, "session_id": session_id}

    except requests.exceptions.Timeout:
        _emit(session_id, "stream_error", error="AIDA API request timed out")
        return {"ok": False, "error": "timeout"}
    except requests.exceptions.ConnectionError:
        _emit(session_id, "stream_error", error="Cannot connect to AIDA API")
        return {"ok": False, "error": "connection_error"}
    except Exception as e:
        _emit(session_id, "stream_error", error=str(e)[:200])
        return {"ok": False, "error": str(e)[:200]}


def convert_bytes_to_markdown(content, filename):
    """Send file bytes to the AIDA Convert API. Returns (markdown, error)."""
    convert_url, convert_key = _get_convert_config()
    if not convert_url or not convert_key:
        return "", "AIDA Convert API is not configured"
    try:
        resp = requests.post(
            f"{convert_url}/api/v1/convert",
            headers={"X-API-Key": convert_key},
            files={"file": (filename, content)},
            data={"output_format": "markdown", "use_vlm": "true", "detect_tables": "true"},
            timeout=300,
        )
    except requests.exceptions.RequestException as e:
        return "", f"Convert API unreachable: {str(e)[:150]}"
    if resp.status_code not in (200, 201):
        return "", f"Convert API error {resp.status_code}: {resp.text[:200]}"
    result = resp.json()
    if result.get("success") is False:
        return "", f"Convert API: {result.get('error') or 'conversion failed'}"
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

    file_doc = frappe.get_doc("File", {"file_url": file_url})
    file_path = file_doc.get_full_path()

    filename = file_url.split("/")[-1]
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{voice_url}/api/v1/transcriptions",
            headers={"X-API-Key": voice_key},
            files={"audio_file": (filename, f)},
            data={"language": "es", "task": "transcribe"},
            timeout=120,
        )

    if resp.status_code not in (200, 201):
        return {"ok": False, "error": f"Voice API error {resp.status_code}: {resp.text[:200]}"}

    result = resp.json()
    text = result.get("text", result.get("transcription", ""))
    return {"ok": True, "text": text, "filename": filename}
