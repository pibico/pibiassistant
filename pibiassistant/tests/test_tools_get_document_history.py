# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""get_document_history: version parsing, masking, permission refusal."""

import json

import frappe

from pibiassistant.plugins.core.tools.get_document_history import GetDocumentHistory
from pibiassistant.tests.base_test import BaseAssistantTest


class TestGetDocumentHistory(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ZZ history todo"}).insert(
            ignore_permissions=True
        )
        self.versions = []

    def tearDown(self):
        frappe.set_user("Administrator")
        for name in self.versions:
            frappe.delete_doc("Version", name, force=True, ignore_permissions=True)
        for dt, filters in (
            ("Comment", {"reference_doctype": "ToDo", "reference_name": self.todo.name}),
            ("Version", {"ref_doctype": "ToDo", "docname": self.todo.name}),
        ):
            for n in frappe.get_all(dt, filters=filters, pluck="name"):
                frappe.delete_doc(dt, n, force=True, ignore_permissions=True)
        frappe.delete_doc("ToDo", self.todo.name, force=True, ignore_permissions=True)
        super().tearDown()

    def _version(self, data, doctype="ToDo", name=None):
        v = frappe.get_doc(
            {"doctype": "Version", "ref_doctype": doctype, "docname": name or self.todo.name, "data": json.dumps(data)}
        ).insert(ignore_permissions=True)
        self.versions.append(v.name)
        return v

    def _run(self, **args):
        args.setdefault("doctype", "ToDo")
        args.setdefault("name", self.todo.name)
        return GetDocumentHistory().execute(args)

    def test_changes_are_listed_with_labels(self):
        self._version({"changed": [["status", "Open", "Closed"], ["zz_gone_field", "a", "b"]]})
        result = self._run()
        self.assertTrue(result["success"], result)
        self.assertEqual(len(result["versions"]), 1)
        entry = result["versions"][0]
        self.assertEqual([c["field"] for c in entry["changed"]], ["status"])
        self.assertEqual((entry["changed"][0]["old"], entry["changed"][0]["new"]), ("Open", "Closed"))
        self.assertTrue(entry["changed"][0]["label"])
        self.assertEqual(entry["user"], "Administrator")

    def test_rows_and_long_values(self):
        self._version({"changed": [["description", "x" * 500, "y"]], "added": [["zz", [{}]]], "removed": []})
        entry = self._run()["versions"][0]
        self.assertLessEqual(len(entry["changed"][0]["old"]), 200)

    def test_credentials_are_masked(self):
        self._version({"changed": [["api_key", "old-secret-value", "new-secret-value"]]}, "User", "Administrator")
        result = self._run(doctype="User", name="Administrator")
        text = json.dumps(result)
        self.assertNotIn("secret-value", text)
        self.assertIn("***", text)

    def test_comments_are_stripped_and_optional(self):
        self.todo.add_comment("Comment", "<p>Hello <b>team</b></p>")
        result = self._run()
        self.assertNotIn("comments_missing", result)
        self.assertEqual(result["comments"][0]["text"], "Hello team")
        only = self._run(include=["versions"])
        self.assertNotIn("comments", only)

    def test_assignments_and_attachments_sections(self):
        result = self._run(include=["assignments", "attachments"])
        self.assertEqual(result["assignments"], [])
        self.assertEqual(result["attachments"], [])

    def test_validation_errors(self):
        self.assertFalse(self._run(include=["bogus"])["success"])
        self.assertFalse(self._run(name="ZZ-nope-123")["success"])
        self.assertFalse(self._run(doctype="No Such Doctype")["success"])

    def test_limit_is_capped(self):
        for i in range(3):
            self._version({"changed": [["status", str(i), "Open"]]})
        self.assertEqual(len(self._run(limit=2)["versions"]), 2)
        self.assertEqual(self._run(limit=9999)["limit"], 50)

    def test_denied_without_read_permission(self):
        self._version({"changed": [["status", "Open", "Closed"]]})
        email = "zz-hist-t1@example.com"
        user = frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": "ZZ Hist", "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
        try:
            frappe.set_user(email)
            with self.enforce_only_for_checks():
                result = self._run(doctype="User", name="Administrator")
            self.assertFalse(result["success"], result)
            self.assertNotIn("versions", result)
        finally:
            frappe.set_user("Administrator")
            frappe.delete_doc("User", user.name, force=True, ignore_permissions=True)
