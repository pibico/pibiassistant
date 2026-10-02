# pibiAssistant - Voice Proxy API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Voice-to-text proxy. Forwards browser audio to the AIDA Voice API
or to AIDA (legacy path). Gates the call on PA Chat being enabled."""

import frappe
from frappe import _
from frappe.utils import cint

from pibiassistant.pibiassistant_chat.gate import is_chat_enabled

from .aida import _transcription_language, post_transcription
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
    lang = _transcription_language(language)
    filename = audio_file.filename or "audio.webm"
    duration_ms = max(cint(duration_ms), 0)

    from pibiassistant.pibiassistant_chat.api.aida import _get_voice_config
    voice_url, voice_key = _get_voice_config()

    if voice_url and voice_key:
        text, error = post_transcription(voice_url, voice_key, filename, audio_bytes, lang, mime_type)
        if error:
            frappe.throw(error)
        return {"text": text, "duration_seconds": duration_ms / 1000}

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
        duration_ms=duration_ms,
        language=lang,
    )
