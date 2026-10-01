# pibiAssistant - Voice Proxy API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Voice-to-text proxy. Forwards browser audio to the AIDA Voice API
or to AIDA (legacy path). Gates the call on PA Chat being enabled."""

from __future__ import annotations

import frappe
import requests
from frappe import _

from pibiassistant.pibiassistant_chat.gate import is_chat_enabled

from ._rate_limits import rate_limit, session_user_or_ip

MAX_AUDIO_BYTES = 10_485_760  # 10 MB


@frappe.whitelist(methods=["POST"])
@rate_limit(session_user_or_ip, limit=20, seconds=60)
def transcribe(duration_ms: int = 0, language: str | None = None) -> dict:
    """Proxy voice transcription to the AIDA Voice API.

    Accepts raw audio via multipart form (field name: "audio").
    """
    if not is_chat_enabled():
        frappe.throw(_("AIDA Chat is disabled."), frappe.PermissionError)

    from .settings import can_use_pao

    access = can_use_pao()
    if not access.get("can_use"):
        frappe.throw(access.get("reason") or _("Cannot use AIDA"), frappe.PermissionError)

    audio_file = frappe.request.files.get("audio")
    if not audio_file:
        frappe.throw(_("No audio file provided."), frappe.ValidationError)

    audio_bytes = audio_file.read()
    if not audio_bytes:
        frappe.throw(_("Audio file is empty."), frappe.ValidationError)
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        frappe.throw(
            _("Audio file too large ({0} bytes, max {1}).").format(len(audio_bytes), MAX_AUDIO_BYTES),
            frappe.ValidationError,
        )

    mime_type = audio_file.mimetype or "audio/webm"
    lang = (language or "").strip() or "es"
    filename = audio_file.filename or "audio.webm"

    from pibiassistant.pibiassistant_chat.api.aida import _get_voice_config
    voice_url, voice_key = _get_voice_config()

    if voice_url and voice_key:
        resp = requests.post(
            f"{voice_url}/api/v1/transcriptions",
            headers={"X-API-Key": voice_key},
            files={"audio_file": (filename, audio_bytes, mime_type)},
            data={"language": lang, "task": "transcribe"},
            timeout=120,
        )
        if resp.status_code not in (200, 201):
            frappe.throw(_("Voice API error {0}: {1}").format(resp.status_code, resp.text[:200]))

        result = resp.json()
        return {"text": result.get("text", result.get("transcription", "")),
                "duration_seconds": int(duration_ms or 0) / 1000}

    # Legacy cloud path
    from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client
    from .auth import _ar_user_id

    client = get_pa_cloud_client()
    if not client:
        frappe.throw(_("AIDA Voice API is not configured. Go to PA Core Settings > AIDA Chat."))

    return client.transcribe_audio(
        audio_bytes=audio_bytes,
        mime_type=mime_type,
        user_id=_ar_user_id(frappe.session.user),
        duration_ms=int(duration_ms or 0),
        language=lang,
    )


def _resolve_default_language() -> str:
    """Fallback used only when the client sent no language hint.

    The browser sends `navigator.language` (and the SPA also reads the
    AR Tenant User profile locale ahead of that). If neither is present —
    a non-browser SDK caller, a stripped form, or a request from an iframe
    that lost its locale — fall back to English. Whisper's auto-detect on
    silent audio is the failure mode we're trying to avoid.
    """
    return "en"
