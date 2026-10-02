"""Profile field caps, transcription language, and the convert/transcribe gate."""

import unittest
from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.pibiassistant_chat.api import aida, profile
from pibiassistant.pibiassistant_chat.api.chat import helpers


class TestProfileCaps(unittest.TestCase):
    def test_over_long_field_is_a_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            profile.update_profile(about="x" * 2001)
        with self.assertRaises(frappe.ValidationError):
            profile.update_profile(display_name="x" * 141)


class TestTranscriptionLanguage(unittest.TestCase):
    def test_language_argument_and_fallbacks(self):
        self.assertEqual(aida._transcription_language("en-US"), "en")
        self.assertEqual(aida._transcription_language("FR"), "fr")
        self.assertEqual(aida._transcription_language("../x"), "es")
        with patch.object(aida.frappe.local, "lang", "ca"):
            self.assertEqual(aida._transcription_language(None), "ca")

    def test_language_reaches_the_voice_api_and_gate_is_checked(self):
        file_doc = MagicMock(file_name="a.mp3", file_url="/files/a.mp3")
        file_doc.get_full_path.return_value = __file__
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"text": "hi"}
        with patch.object(aida, "_get_voice_config", return_value=("http://v", "k")), patch.object(
            aida.frappe, "get_doc", return_value=file_doc
        ), patch.object(aida.os.path, "getsize", return_value=10), patch.object(
            aida.requests, "post", return_value=resp
        ) as post:
            frappe.set_user("Administrator")
            aida.transcribe_audio("/files/a.mp3", language="en")
        self.assertEqual(post.call_args.kwargs["data"]["language"], "en")

    def test_convert_document_requires_access_and_size_cap(self):
        with patch.object(aida, "_assert_can_use_aida", side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                aida.convert_document("/files/a.pdf")
        file_doc = MagicMock(file_name="a.pdf")
        file_doc.get_full_path.return_value = __file__
        with patch.object(aida, "_assert_can_use_aida"), patch.object(aida.frappe, "get_doc", return_value=file_doc), patch.object(
            aida.os.path, "getsize", return_value=aida._AUDIO_MAX_BYTES + 1
        ):
            with self.assertRaises(frappe.ValidationError):
                aida.convert_document("/files/a.pdf")


class TestAttachmentNotes(unittest.TestCase):
    def test_unreadable_file_is_reported_to_the_model(self):
        info = frappe._dict(name="F1", file_name="a.pdf", file_url="/files/a.pdf", file_size=10)
        with patch.object(helpers.frappe, "get_all", return_value=[info]), patch(
            "pibiassistant.plugins.data_science.tools.extract_file_content.ExtractFileContent.execute",
            return_value={"success": False, "error": "unreadable"},
        ):
            out = helpers._extract_file_attachments("MSG")
        self.assertIn("could not be read", out)
        self.assertIn("/files/a.pdf", out)


if __name__ == "__main__":
    unittest.main()
