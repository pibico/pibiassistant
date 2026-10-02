# pibiAssistant - orphaned chat attachment sweep tests
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

import frappe
from frappe.utils import add_to_date, now

from pibiassistant.pibiassistant_chat.gate import clear_chat_gate_cache
from pibiassistant.pibiassistant_chat.scheduler.attachment_sweep import (
    sweep_orphan_chat_attachments,
)
from pibiassistant.tests.base_test import BaseAssistantTest

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class TestChatAttachmentCustomField(BaseAssistantTest):
    def test_pending_flag_field_exists(self):
        df = frappe.get_meta("File").get_field("pa_pending_chat_attachment")
        self.assertIsNotNone(df, "File-pa_pending_chat_attachment fixture is not installed")
        self.assertEqual(df.fieldtype, "Check")


class TestChatAttachmentSweep(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.db.set_single_value("PA Core Settings", "enable_pa_chat", 1)
        frappe.clear_cache()
        clear_chat_gate_cache()

    def _pending_file(self, age_hours: int, file_name: str = "shot.png") -> str:
        f = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": file_name,
                "content": PNG,
                "is_private": 1,
                "folder": "Home/Attachments",
                "pa_pending_chat_attachment": 1,
            }
        )
        f.insert(ignore_permissions=True)
        frappe.db.set_value(
            "File", f.name, "creation", add_to_date(now(), hours=-age_hours), update_modified=False
        )
        return f.name

    def test_deletes_pending_older_than_24h(self):
        orphan = self._pending_file(30)
        result = sweep_orphan_chat_attachments()
        self.assertFalse(frappe.db.exists("File", orphan))
        self.assertEqual(result["status"], "success")
        self.assertGreaterEqual(result["files_deleted"], 1)

    def test_keeps_recent_pending(self):
        recent = self._pending_file(2)
        sweep_orphan_chat_attachments()
        self.assertTrue(frappe.db.exists("File", recent))

    def test_keeps_cleared_flag_regardless_of_age(self):
        sent = self._pending_file(30)
        frappe.db.set_value("File", sent, "pa_pending_chat_attachment", 0, update_modified=False)
        sweep_orphan_chat_attachments()
        self.assertTrue(frappe.db.exists("File", sent))

    def test_keeps_linked_file_even_if_flag_stuck(self):
        # A file that reached a message backs a live conversation. The
        # attached_to_name guard must protect it even when the flag failed to
        # clear — the flag alone is not a safe delete key.
        stuck = self._pending_file(30)
        frappe.db.set_value(
            "File",
            stuck,
            {"attached_to_doctype": "PA Chat Message", "attached_to_name": "FACMSG-TEST-0001"},
            update_modified=False,
        )
        sweep_orphan_chat_attachments()
        self.assertTrue(frappe.db.exists("File", stuck))

    def test_noop_when_chat_disabled(self):
        orphan = self._pending_file(30)
        frappe.db.set_single_value("PA Core Settings", "enable_pa_chat", 0)
        frappe.clear_cache()
        clear_chat_gate_cache()

        result = sweep_orphan_chat_attachments()

        self.assertEqual(result["status"], "chat_module_disabled")
        self.assertTrue(frappe.db.exists("File", orphan))


class TestDebugBundleSweep(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.db.set_single_value("PA Core Settings", "enable_pa_chat", 1)
        frappe.clear_cache()
        clear_chat_gate_cache()

    def _bundle(self, age_hours, name="debug-bundle-ZZ-sweep.zip"):
        f = frappe.get_doc(
            {"doctype": "File", "file_name": name, "content": b"PK-" + frappe.generate_hash(length=8).encode(), "is_private": 1}
        ).insert(ignore_permissions=True)
        frappe.db.set_value("File", f.name, "creation", add_to_date(now(), hours=-age_hours), update_modified=False)
        self.addCleanup(lambda: frappe.db.exists("File", f.name) and frappe.delete_doc("File", f.name, force=True, ignore_permissions=True))
        return f.name

    def test_old_bundles_are_reaped_recent_ones_and_other_files_stay(self):
        old, recent = self._bundle(30), self._bundle(2)
        other = self._bundle(30, name="ZZ-keep-me.zip")
        sweep_orphan_chat_attachments()
        self.assertFalse(frappe.db.exists("File", old))
        self.assertTrue(frappe.db.exists("File", recent))
        self.assertTrue(frappe.db.exists("File", other))
