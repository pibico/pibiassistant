"""Session ids must be validated strings: a list/dict reaching an ORM filter would match other conversations."""

import inspect
from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.api.chat import cancel, debug_bundle, hitl, messages, sessions
from pibiassistant.pibiassistant_chat.api.settings import uploads
from pibiassistant.tests.base_test import BaseAssistantTest

BAD_IDS = (["like", "%"], {"a": 1}, 5, "has space", "x" * 101, "")


class TestChatApiSessionIdTypes(BaseAssistantTest):
    def _assert_rejected(self, fn, *extra):
        for bad in BAD_IDS:
            with self.subTest(fn=fn.__name__, bad=bad):
                with patch.object(frappe.db, "set_value") as set_value:
                    with self.assertRaises((frappe.ValidationError, frappe.exceptions.FrappeTypeError)):
                        fn(bad, *extra)
                set_value.assert_not_called()

    def test_session_endpoints_reject_non_string_ids(self):
        for fn in (
            sessions.archive_session,
            sessions.delete_session,
            sessions.continue_archived_session,
            sessions.get_session_history,
            cancel.cancel_stream,
            hitl.get_pending_interrupt,
            debug_bundle.export_debug_bundle,
        ):
            if fn is debug_bundle.export_debug_bundle:
                with patch.object(frappe, "get_roles", return_value=["System Manager"]):
                    self._assert_rejected(fn)
            else:
                self._assert_rejected(fn)

    def test_send_message_rejects_non_string_message(self):
        fn = getattr(messages.send_message, "__wrapped__", messages.send_message)
        for bad in (["x"], {"a": 1}, 5):
            with self.assertRaises(frappe.ValidationError):
                fn(session_id="zz-types", message=bad)

    def test_whitelisted_modules_keep_frappe_type_validation(self):
        for module in (sessions, cancel, messages, uploads, debug_bundle):
            self.assertNotIn("from __future__ import annotations", inspect.getsource(module))
            for fn in (v for v in vars(module).values() if callable(v) and getattr(v, "whitelisted", False)):
                for p in inspect.signature(fn).parameters.values():
                    self.assertNotIsInstance(p.annotation, str, f"{fn.__name__}.{p.name}")
