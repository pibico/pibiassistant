"""rename_document: refuses what cannot or must not be renamed, and renames a Contact for real."""

import unittest

import frappe

from pibiassistant.plugins.core.tools.rename_document import DocumentRename, check_rename
from pibiassistant.pibiassistant_chat.api.chat.aida_tools import WRITE_TOOLS, _approval_card


class TestRenameDocument(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.created = []

    def tearDown(self):
        frappe.set_user("Administrator")
        for name in self.created:
            if frappe.db.exists("Contact", name):
                frappe.delete_doc("Contact", name, force=True, ignore_permissions=True)
        frappe.db.commit()

    def _contact(self, first, last):
        doc = frappe.get_doc({"doctype": "Contact", "first_name": first, "last_name": last}).insert(ignore_permissions=True)
        self.created.append(doc.name)
        frappe.db.commit()
        return doc.name

    def test_blocked_and_unsupported_doctypes(self):
        for dt in ("User", "Company", "DocType", "Role", "Custom DocPerm"):
            self.assertIn("cannot be renamed", check_rename(dt, "x", "y") or "", dt)
        self.assertIn("does not allow renaming", check_rename("ToDo", "x", "y") or "")

    def test_same_missing_and_existing_names(self):
        self.assertIn("same as the current", check_rename("Contact", "a", "a"))
        self.assertIn("required", check_rename("Contact", "a", "  "))
        self.assertIn("not found", check_rename("Contact", "ZZ-missing-contact", "ZZ-other"))
        a = self._contact("ZZRenA", "One")
        b = self._contact("ZZRenB", "Two")
        self.assertIn("already exists", check_rename("Contact", a, b))

    def test_renames_a_contact(self):
        old = self._contact("ZZRen", "Old")
        result = DocumentRename().execute({"doctype": "Contact", "name": old, "new_name": "ZZRen New Name"})
        self.assertTrue(result["success"], result)
        self.created.append(result["new_name"])
        self.assertEqual(result["new_name"], "ZZRen New Name")
        self.assertFalse(frappe.db.exists("Contact", old))
        self.assertTrue(frappe.db.exists("Contact", "ZZRen New Name"))
        self.assertIsInstance(result["references_updated"], int)

    def test_user_without_write_permission_is_refused(self):
        old = self._contact("ZZRenP", "Perm")
        frappe.set_user("Guest")
        result = DocumentRename().execute({"doctype": "Contact", "name": old, "new_name": "ZZRen Guest"})
        frappe.set_user("Administrator")
        self.assertFalse(result["success"])
        self.assertTrue(frappe.db.exists("Contact", old))

    def test_chat_treats_it_as_a_write_with_an_informative_card(self):
        self.assertIn("rename_document", WRITE_TOOLS)
        old = self._contact("ZZRenC", "Card")
        card = _approval_card(
            {"interrupt_id": "i1", "name": "rename_document", "arguments": {"doctype": "Contact", "name": old, "new_name": "ZZ Card New"}}
        )
        self.assertIn("-> 'ZZ Card New'", card["reason"]["description"])
        self.assertIn("reference(s)", card["reason"]["description"])
        self.assertTrue(card["reason"]["action"].startswith("Rename a document"))
