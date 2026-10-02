"""Prompt Template search/listing helpers must honour the permission query."""

import frappe

from pibiassistant.pibiassistant_core.doctype.prompt_template import prompt_template as pt
from pibiassistant.tests.base_test import BaseAssistantTest


class TestPromptTemplatePermissions(BaseAssistantTest):
    USER = "zz_prompt_perm_user@example.com"
    PROMPT_ID = "zz_private_prompt_probe"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if frappe.db.exists("User", cls.USER):
            frappe.delete_doc("User", cls.USER, force=True)
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": cls.USER,
                "first_name": "ZZ",
                "enabled": 1,
                "new_password": "test_password_123",
                "user_type": "System User",
            }
        )
        user.insert(ignore_permissions=True)
        user.reload()
        user.roles = [r for r in user.roles if r.role in ("All", "Guest")]
        user.save(ignore_permissions=True)
        frappe.db.set_value("User", cls.USER, "user_type", "System User")
        frappe.clear_cache(user=cls.USER)

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        if frappe.db.exists("User", cls.USER):
            frappe.delete_doc("User", cls.USER, force=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        doc = frappe.get_doc(
            {
                "doctype": "Prompt Template",
                "prompt_id": self.PROMPT_ID,
                "title": "ZZ Private Probe",
                "description": "fixture",
                "template_content": "Hi {{ x }}",
                "rendering_engine": "Jinja2",
                "status": "Draft",
                "visibility": "Private",
                "owner_user": "Administrator",
                "arguments": [{"argument_name": "x", "argument_type": "string", "is_required": 1}],
            }
        )
        doc.flags.ignore_permissions = True
        doc.insert()
        self.name = doc.name

    def tearDown(self):
        frappe.set_user("Administrator")
        if frappe.db.exists("Prompt Template", self.name):
            frappe.delete_doc("Prompt Template", self.name, force=True, ignore_permissions=True)
        super().tearDown()

    def test_search_hides_other_users_private_draft(self):
        frappe.set_user(self.USER)
        found = pt.search_prompts(query="ZZ Private Probe", status="Draft")
        self.assertEqual([p.name for p in found], [])

    def test_version_history_denied_for_invisible_template(self):
        frappe.set_user(self.USER)
        with self.assertRaises(frappe.PermissionError):
            pt.get_version_history(self.name)

    def test_version_history_allowed_for_admin(self):
        self.assertIsInstance(pt.get_version_history(self.name), list)

    def test_limit_is_clamped(self):
        self.assertIsInstance(pt.search_prompts(limit=-5), list)
        self.assertIsInstance(pt.get_popular_prompts(limit=-5), list)
        self.assertEqual(pt.clamp_limit("abc", 20, 100), 20)
        self.assertLessEqual(len(pt.get_popular_prompts(limit=100000)), 100)
