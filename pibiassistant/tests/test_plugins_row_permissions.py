"""list_documents and search_documents must not leak rows the user cannot read (private Files)."""

import frappe

from pibiassistant.plugins.core.tools.list_documents import DocumentList, invalid_filter_message
from pibiassistant.plugins.core.tools.search_documents import SearchDocuments
from pibiassistant.plugins.limits import clamp_limit
from pibiassistant.tests.base_test import BaseAssistantTest

OTHER = "zz-rowperm@example.com"


class TestRowPermissions(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        if not frappe.db.exists("User", OTHER):
            frappe.get_doc(
                {"doctype": "User", "email": OTHER, "first_name": "ZZ", "send_welcome_email": 0,
                 "roles": [{"role": "Desk User"}]}
            ).insert()
        self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ZZ perm"}).insert()
        self.file = frappe.get_doc(
            {"doctype": "File", "file_name": "zz-private-rowperm.txt", "content": b"zz",
             "is_private": 1, "attached_to_doctype": "ToDo", "attached_to_name": self.todo.name}
        ).insert()
        self.addCleanup(frappe.set_user, "Administrator")

    def _names(self, user, tool, args, key):
        frappe.set_user(user)
        result = tool.execute(args)
        self.assertTrue(result["success"], result)
        return [r["name"] for r in result[key]], result

    def test_list_hides_foreign_private_file(self):
        args = {"doctype": "File", "filters": {"file_name": "zz-private-rowperm.txt"}, "fields": ["file_name"]}
        names, _ = self._names(OTHER, DocumentList(), args, "data")
        self.assertNotIn(self.file.name, names)
        names, result = self._names("Administrator", DocumentList(), args, "data")
        self.assertIn(self.file.name, names)

    def test_search_hides_foreign_private_file(self):
        args = {"query": "zz-private-rowperm", "doctype": "File"}
        names, _ = self._names(OTHER, SearchDocuments(), args, "results")
        self.assertNotIn(self.file.name, names)
        names, _ = self._names("Administrator", SearchDocuments(), args, "results")
        self.assertIn(self.file.name, names)

    def test_limit_below_one_uses_default(self):
        self.assertEqual(clamp_limit(0, 20, 1000), 20)
        self.assertEqual(clamp_limit(-5, 20, 1000), 20)
        self.assertEqual(clamp_limit(5000, 20, 1000), 1000)
        self.assertEqual(clamp_limit(3, 20, 1000), 3)

    def test_malformed_filters_rejected(self):
        self.assertIn("between", invalid_filter_message("ToDo", {"creation": ["between", ["2026-01-01"]]}))
        self.assertIn("not a number", invalid_filter_message("Customer", {"disabled": "abc"}))
        self.assertIn("list", invalid_filter_message("ToDo", {"name": ["in", 5]}))
        self.assertIsNone(invalid_filter_message("Customer", {"disabled": 0}))
        self.assertIsNone(invalid_filter_message("ToDo", {"creation": ["between", ["2026-01-01", "2026-02-01"]]}))
        self.assertIsNone(invalid_filter_message("ToDo", [["ToDo", "status", "=", "Open"]]))
        result = DocumentList().execute({"doctype": "Customer", "filters": {"disabled": "abc"}})
        self.assertFalse(result["success"])
