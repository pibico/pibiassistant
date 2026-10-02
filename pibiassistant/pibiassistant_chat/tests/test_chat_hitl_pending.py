"""In AIDA mode a saved approval is returned to its owner (and only to them) so the card survives a reload."""

import unittest
from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.api.chat import aida_tools, hitl

SID = "ZZ-hitl-pending"


class TestPendingInterrupt(unittest.TestCase):
    def tearDown(self):
        frappe.cache().delete_value(aida_tools._pending_key(SID))

    def _save(self, user):
        call = {"name": "create_document", "arguments": {"doctype": "ToDo"}, "tool_id": "t1", "interrupt_id": "i1", "pending": True}
        aida_tools._save_pending(SID, {"user": user, "calls": [call]})

    def test_owner_sees_the_card_other_user_does_not(self):
        self._save("Administrator")
        with patch("pibiassistant.pibiassistant_chat.api.chat.aida_stream.is_aida_mode", return_value=True):
            frappe.set_user("Administrator")
            owner = hitl.get_pending_interrupt(SID)
            frappe.set_user("zz-other@example.com")
            other = hitl.get_pending_interrupt(SID)
            frappe.set_user("Administrator")
        self.assertTrue(owner["pending"])
        self.assertEqual(owner["event"]["tool_id"], "t1")
        self.assertEqual(owner["event"]["interrupts"][0]["id"], "i1")
        self.assertTrue(owner["expires_at"])
        self.assertEqual(other, {"pending": False})

    def test_nothing_pending(self):
        with patch("pibiassistant.pibiassistant_chat.api.chat.aida_stream.is_aida_mode", return_value=True):
            self.assertEqual(hitl.get_pending_interrupt(SID), {"pending": False})


if __name__ == "__main__":
    unittest.main()
