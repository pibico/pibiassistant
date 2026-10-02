"""Plugin tool fixes: aggregate wording, approvals validation, linked documents, PDF template."""

import frappe

from pibiassistant.plugins.core.tools.aggregate_documents import AggregateDocuments
from pibiassistant.plugins.core.tools.get_linked_documents import GetLinkedDocuments
from pibiassistant.plugins.core.tools.get_pending_approvals import GetPendingApprovals
from pibiassistant.tests.base_test import BaseAssistantTest


class TestPluginMiscFixes(BaseAssistantTest):
    def test_aggregate_description_names_real_parameter(self):
        description = AggregateDocuments().description
        self.assertIn("aggregates sum", description)
        self.assertNotIn("metrics", description)

    def test_pending_approvals_unknown_doctype_is_error(self):
        result = GetPendingApprovals().execute({"doctype": "ZZ Not A DocType"})
        self.assertFalse(result["success"])
        self.assertIn("ZZ Not A DocType", result["error"])

    def test_pending_approvals_negative_limit_still_works(self):
        self.assertTrue(GetPendingApprovals().execute({"limit": -1})["success"])

    def test_pdf_template_translated_footer_and_contrast(self):
        path = frappe.get_app_path("pibiassistant", "plugins", "pao", "tools", "templates", "document_pdf.html")
        with open(path) as f:
            source = f.read()
        self.assertNotIn("#999", source)
        html = frappe.render_template(source, {"body": "", "generated_date": "X"})
        self.assertIn("Generated on X", html)


class TestGetLinkedDocuments(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.email = "zz-linked-user@example.com"
        if not frappe.db.exists("User", self.email):
            frappe.get_doc(
                {"doctype": "User", "email": self.email, "first_name": "ZZ", "send_welcome_email": 0}
            ).insert()
        self.addCleanup(self._cleanup)
        self.linked = frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": "User",
                "reference_name": self.email,
                "content": "ZZ linked comment",
            }
        ).insert().name

    def _cleanup(self):
        frappe.set_user("Administrator")
        frappe.db.delete("Comment", {"reference_doctype": "User", "reference_name": self.email})
        frappe.delete_doc("User", self.email, force=True, ignore_permissions=True)

    def test_finds_linked_document(self):
        result = GetLinkedDocuments().execute({"doctype": "User", "name": self.email})
        self.assertTrue(result["success"], result)
        self.assertIn(self.linked, [r["name"] for r in result["linked"].get("Comment", [])])

    def test_filter_and_missing(self):
        only = GetLinkedDocuments().execute(
            {"doctype": "User", "name": self.email, "linked_doctype": "ToDo"}
        )
        self.assertEqual(only["linked"], {})
        self.assertFalse(GetLinkedDocuments().execute({"doctype": "User", "name": "zz-none@example.com"})["success"])
        self.assertFalse(GetLinkedDocuments().execute({"doctype": "User"})["success"])

    def test_permission_denied_for_unreadable_doc(self):
        frappe.set_user(self.email)
        try:
            result = GetLinkedDocuments().execute({"doctype": "User", "name": "Administrator"})
        finally:
            frappe.set_user("Administrator")
        self.assertFalse(result["success"], result)
