"""Voice and convert upstream failures must never leak internals or raise raw errors."""

from unittest.mock import MagicMock, patch

import frappe
import requests

from pibiassistant.pibiassistant_chat.api import aida, voice
from pibiassistant.tests.base_test import BaseAssistantTest


def _resp(status=200, text="", json_value=None, json_error=False):
    r = MagicMock(status_code=status, text=text)
    if json_error:
        r.json.side_effect = ValueError("bad json")
    else:
        r.json.return_value = json_value or {}
    return r


class TestVoiceProxyErrors(BaseAssistantTest):
    def _post(self):
        return aida.post_transcription("https://voice.internal", "k", "a.webm", b"x", "es", "audio/webm")

    def test_connection_error_is_generic_and_logged(self):
        with (
            patch.object(aida.requests, "post", side_effect=requests.exceptions.ConnectionError("https://voice.internal down")),
            patch.object(frappe, "log_error") as log,
        ):
            text, error = self._post()
        self.assertEqual(text, "")
        self.assertNotIn("voice.internal", error)
        log.assert_called_once()

    def test_timeout_is_generic(self):
        with patch.object(aida.requests, "post", side_effect=requests.exceptions.Timeout()), patch.object(frappe, "log_error"):
            _text, error = self._post()
        self.assertTrue(error)

    def test_non_200_body_is_never_echoed(self):
        with (
            patch.object(aida.requests, "post", return_value=_resp(401, "bad key sk-SECRET tenant=acme")),
            patch.object(frappe, "log_error"),
        ):
            _text, error = self._post()
        self.assertNotIn("SECRET", error)
        self.assertNotIn("acme", error)
        self.assertIn("401", error)

    def test_invalid_json_is_handled(self):
        with patch.object(aida.requests, "post", return_value=_resp(200, json_error=True)):
            _text, error = self._post()
        self.assertTrue(error)

    def test_success_returns_text(self):
        with patch.object(aida.requests, "post", return_value=_resp(200, json_value={"text": "hola"})):
            self.assertEqual(self._post(), ("hola", ""))

    def test_hostile_language_is_normalised(self):
        self.assertEqual(aida._transcription_language("es\r\nX-Evil: 1"), "es")
        self.assertEqual(aida._transcription_language("zz-ZZ"), "zz")
        self.assertEqual(aida._transcription_language("!!"), "es")

    def test_transcribe_endpoint_survives_bad_duration_and_language(self):
        audio = MagicMock(mimetype="audio/webm", filename="a.webm")
        audio.read.return_value = b"abc"
        request = MagicMock(files={"audio": audio})
        sent = {}

        def fake_post(*a, **kw):
            sent.update(kw["data"])
            return _resp(200, json_value={"text": "ok"})

        with (
            patch.object(frappe, "request", request, create=True),
            patch("pibiassistant.pibiassistant_chat.api.voice.is_chat_enabled", return_value=True),
            patch("pibiassistant.pibiassistant_chat.api.settings.can_use_pao", return_value={"can_use": True}),
            patch("pibiassistant.pibiassistant_chat.api.aida._get_voice_config", return_value=("https://v", "k")),
            patch.object(aida.requests, "post", side_effect=fake_post),
        ):
            out = voice.transcribe.__wrapped__(duration_ms="abc", language="es\r\nEvil")
        self.assertEqual(sent["language"], "es")
        self.assertEqual(out["duration_seconds"], 0)

    def test_convert_unreachable_and_error_bodies_are_generic(self):
        with (
            patch.object(aida, "_get_convert_config", return_value=("https://c.internal", "k")),
            patch.object(frappe, "log_error"),
        ):
            with patch.object(aida.requests, "post", side_effect=requests.exceptions.ConnectionError("https://c.internal")):
                _md, error = aida.convert_bytes_to_markdown(b"x", "a.pdf")
            self.assertNotIn("c.internal", error)
            with patch.object(aida.requests, "post", return_value=_resp(500, "trace sk-SECRET")):
                _md, error = aida.convert_bytes_to_markdown(b"x", "a.pdf")
            self.assertNotIn("SECRET", error)
            with patch.object(aida.requests, "post", return_value=_resp(200, json_error=True)):
                _md, error = aida.convert_bytes_to_markdown(b"x", "a.pdf")
            self.assertTrue(error)
