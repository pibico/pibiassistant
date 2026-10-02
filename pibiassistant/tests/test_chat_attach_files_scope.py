"""Composer uploads link to the chat message; files attached to business documents must not move."""

from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.api.chat.helpers import _attach_files_to_message
from pibiassistant.tests.base_test import BaseAssistantTest


class TestChatAttachFilesScope(BaseAssistantTest):
    def _file(self, name, **kw):
        doc = frappe.get_doc(
            {"doctype": "File", "file_name": name, "content": b"hello", "is_private": 1, **kw}
        ).insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "File", doc.name, force=1, ignore_permissions=True)
        return doc

    def test_only_pending_uploads_are_linked(self):
        todo = frappe.get_doc({"doctype": "ToDo", "description": "ZZ attach scope"}).insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "ToDo", todo.name, force=1, ignore_permissions=True)
        attached = self._file(
            "zz-attached.txt", attached_to_doctype="ToDo", attached_to_name=todo.name
        )
        pending = self._file("zz-pending.txt", pa_pending_chat_attachment=1)
        with patch.object(frappe.db, "commit"):
            linked = _attach_files_to_message([attached.file_url, pending.file_url], "FAKEMSG")
        self.assertEqual(linked, 1)
        row = frappe.db.get_value(
            "File", attached.name, ["attached_to_doctype", "attached_to_name"], as_dict=True
        )
        self.assertEqual((row.attached_to_doctype, row.attached_to_name), ("ToDo", todo.name))
        row = frappe.db.get_value(
            "File", pending.name, ["attached_to_doctype", "attached_to_name", "pa_pending_chat_attachment"], as_dict=True
        )
        self.assertEqual((row.attached_to_doctype, row.attached_to_name), ("PA Chat Message", "FAKEMSG"))
        self.assertEqual(row.pa_pending_chat_attachment, 0)
