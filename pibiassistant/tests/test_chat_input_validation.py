"""Client input to the chat endpoints is validated, not left to blanket excepts and Error Log noise."""

import uuid
from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.pibiassistant_chat.api import aida, analytics, privacy, support
from pibiassistant.pibiassistant_chat.api.chat import messages, sessions
from pibiassistant.pibiassistant_chat.api.settings import uploads
from pibiassistant.tests.base_test import BaseAssistantTest


class TestChatInputValidation(BaseAssistantTest):
    def test_archived_limit_limit_is_clamped_or_rejected_without_log(self):
        with patch.object(frappe, "log_error") as log:
            for value in (-5, 10**9, 0, 5):
                self.assertIsInstance(sessions.get_archived_sessions(value), list)
            with self.assertRaises((frappe.ValidationError, frappe.exceptions.FrappeTypeError)):
                sessions.get_archived_sessions("abc")
        log.assert_not_called()

    def test_models_refresh_garbage_is_not_a_500(self):
        with patch.object(aida, "_assert_can_use_aida"), patch.object(aida, "_get_aida_config", return_value=("", "", "", "")):
            self.assertFalse(aida.get_models(refresh="abc")["success"])

    def _send(self, **kw):
        fn = getattr(messages.send_message, "__wrapped__", messages.send_message)
        return fn(session_id=str(uuid.uuid4()), message="hi", **kw)

    def test_send_message_rejects_non_object_context(self):
        for bad in ("[1,2]", '"x"', "5"):
            with self.assertRaises(frappe.ValidationError):
                self._send(context=bad)

    def test_send_message_rejects_malformed_attachments(self):
        for bad in ('{"a":1}', '["x"]', "5"):
            with self.assertRaises(frappe.ValidationError):
                self._send(attachments=bad)

    def test_invalid_pdf_upload_gives_translated_error_without_log(self):
        upload = MagicMock(mimetype="application/pdf", filename="bad.pdf")
        upload.read.return_value = b"%PDF-1.4\nnot really a pdf"
        request = MagicMock(files={"file": upload})
        with (
            patch.object(frappe, "request", request, create=True),
            patch.object(frappe, "log_error") as log,
            patch("pibiassistant.pibiassistant_chat.api.settings.access.can_use_pao", return_value={"can_use": True}),
        ):
            fn = getattr(uploads.upload_message_file, "__wrapped__", uploads.upload_message_file)
            with self.assertRaises(frappe.ValidationError) as ctx:
                fn()
        self.assertNotIn("pypdf", str(ctx.exception).lower())
        log.assert_not_called()
        self.assertFalse(frappe.get_all("File", filters={"file_name": "bad.pdf", "pa_pending_chat_attachment": 1}))

    def test_cloud_only_modules_use_the_shared_client_helper(self):
        from pibiassistant.pibiassistant_chat.api._helpers import cloud_client_or_throw

        with patch("pibiassistant.pibiassistant_chat.pa_cloud_client.get_pa_cloud_client", return_value=None):
            with self.assertRaises(frappe.ValidationError):
                cloud_client_or_throw()
        for module in (support, privacy, analytics):
            self.assertFalse(hasattr(module, "_get_client"))

    def test_bad_base64_upload_is_a_validation_error_without_log(self):
        fn = getattr(uploads.upload_message_file, "__wrapped__", uploads.upload_message_file)
        with (
            patch.object(frappe, "request", MagicMock(files={}), create=True),
            patch.object(frappe, "log_error") as log,
            patch("pibiassistant.pibiassistant_chat.api.settings.access.can_use_pao", return_value={"can_use": True}),
        ):
            with self.assertRaises(frappe.ValidationError) as ctx:
                fn(file_data="abc", file_name="a.pdf")
            self.assertNotIn("base64-encoded", str(ctx.exception))
            for bad in (5, ["x"]):
                with self.assertRaises((frappe.ValidationError, frappe.exceptions.FrappeTypeError)):
                    fn(file_data=bad, file_name="a.pdf")
        log.assert_not_called()
