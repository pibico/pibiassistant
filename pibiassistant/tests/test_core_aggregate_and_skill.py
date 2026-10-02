# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""aggregate_documents, get_skill and the compact get_doctype_info answer."""

import json

import frappe

from pibiassistant.plugins.core.tools.aggregate_documents import AggregateDocuments
from pibiassistant.plugins.core.tools.get_doctype_info import GetDoctypeInfo
from pibiassistant.plugins.core.tools.get_skill import GetSkill
from pibiassistant.tests.base_test import BaseAssistantTest

CHAT_TRUNCATION = 12000


class TestAggregateDocuments(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.todos = [
            frappe.get_doc({"doctype": "ToDo", "description": f"ZZ agg {i}", "status": status}).insert(
                ignore_permissions=True
            )
            for i, status in enumerate(["Open", "Open", "Closed"])
        ]

    def tearDown(self):
        for todo in self.todos:
            frappe.delete_doc("ToDo", todo.name, force=True, ignore_permissions=True)
        super().tearDown()

    def _run(self, **args):
        args.setdefault("doctype", "ToDo")
        args.setdefault("filters", {"description": ["like", "ZZ agg %"]})
        return AggregateDocuments().execute(args)

    def test_group_by_status_counts(self):
        result = self._run(group_by="status")
        self.assertTrue(result["success"], result)
        counts = {row["status"]: row["count"] for row in result["data"]}
        self.assertEqual(counts, {"Open": 2, "Closed": 1})

    def test_total_count_without_group(self):
        result = self._run()
        self.assertEqual(result["data"], [{"count": 3}])

    def test_rejects_unknown_field_function_and_order(self):
        self.assertFalse(self._run(group_by="nonexistent")["success"])
        self.assertFalse(self._run(aggregates=[{"function": "sum", "field": "status"}])["success"])
        self.assertFalse(self._run(aggregates=[{"function": "median", "field": "idx"}])["success"])
        self.assertFalse(self._run(group_by="status", order_by="count; drop table x")["success"])

    def test_sum_numeric_field(self):
        result = self._run(aggregates=[{"function": "sum", "field": "idx"}, {"function": "max", "field": "idx"}])
        self.assertTrue(result["success"], result)
        self.assertEqual(result["columns"], ["sum_idx", "max_idx"])

    def test_denied_without_read_permission(self):
        email = "zz-agg-o3@example.com"
        user = frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": "ZZ Agg", "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
        try:
            frappe.set_user(email)
            with self.enforce_only_for_checks():
                result = AggregateDocuments().execute({"doctype": "Sales Invoice"})
            self.assertFalse(result["success"], result)
        finally:
            frappe.set_user("Administrator")
            frappe.delete_doc("User", user.name, force=True, ignore_permissions=True)


class TestGetSkill(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.skill_ids = []
        for skill_id, status in (("zz-o3-published", "Published"), ("zz-o3-draft", "Draft")):
            doc = frappe.get_doc(
                {
                    "doctype": "PA Skill",
                    "skill_id": skill_id,
                    "title": f"ZZ {skill_id}",
                    "status": status,
                    "skill_type": "Workflow",
                    "visibility": "Public",
                    "owner_user": "Administrator",
                    "description": "ZZ test skill",
                    "content": "step one",
                }
            ).insert(ignore_permissions=True)
            self.skill_ids.append(doc.name)

    def tearDown(self):
        for name in self.skill_ids:
            frappe.delete_doc("PA Skill", name, force=True, ignore_permissions=True)
        super().tearDown()

    def test_admin_lists_and_reads(self):
        listed = GetSkill().execute({"query": "ZZ zz-o3"})
        self.assertEqual({s["skill_id"] for s in listed["skills"]}, {"zz-o3-published", "zz-o3-draft"})
        read = GetSkill().execute({"skill_id": "zz-o3-published"})
        self.assertEqual(read["skill"]["content"], "step one")

    def test_non_admin_sees_only_published(self):
        email = "zz-skill-o3@example.com"
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "ZZ Skill",
                "send_welcome_email": 0,
                "roles": [{"role": "PA User"}],
            }
        ).insert(ignore_permissions=True)
        try:
            frappe.set_user(email)
            listed = GetSkill().execute({"query": "ZZ zz-o3"})
            self.assertTrue(listed["success"], listed)
            self.assertEqual([s["skill_id"] for s in listed["skills"]], ["zz-o3-published"])
            self.assertFalse(GetSkill().execute({"skill_id": "zz-o3-draft"})["success"])
        finally:
            frappe.set_user("Administrator")
            frappe.delete_doc("User", user.name, force=True, ignore_permissions=True)


class TestCompactDoctypeInfo(BaseAssistantTest):
    def _info(self, **args):
        return GetDoctypeInfo().execute({"doctype": args.pop("doctype"), **args})

    def test_big_doctypes_fit_chat_truncation_with_child_tables(self):
        for doctype in ("Purchase Invoice", "Sales Invoice", "Timesheet", "Quotation"):
            result = self._info(doctype=doctype)
            self.assertTrue(result["success"], result)
            self.assertLess(len(json.dumps(result, default=str)), CHAT_TRUNCATION, doctype)
            self.assertTrue(result["child_tables"], doctype)
            self.assertTrue(result["required_fields"], doctype)

    def test_child_table_and_fieldnames_detail(self):
        detail = self._info(doctype="Sales Invoice", child_table="items")
        names = {f["fieldname"] for f in detail["child_table"]["fields"]}
        self.assertIn("item_code", names)
        self.assertFalse(self._info(doctype="Sales Invoice", child_table="nope")["success"])
        fields = self._info(doctype="Sales Invoice", fieldnames=["customer"])["field_details"]
        self.assertEqual(fields[0]["fieldname"], "customer")

    def test_include_layout_keeps_verbose_shape(self):
        result = self._info(doctype="User", include_layout=True)
        self.assertTrue(any(f["fieldtype"] == "Section Break" for f in result["fields"]))
        self.assertIn("link_fields", result)
