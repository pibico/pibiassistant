import json
import os
import unittest

import frappe

APP = frappe.get_app_path("pibiassistant")
DOCS = os.path.join(os.path.dirname(APP), "docs", "skills")
NEW_SKILLS = (
    "bank-reconciliation",
    "journal-entry-month-close",
    "item-creation",
    "manufacturing-work-order",
    "hr-leave-payroll",
    "issue-followup",
    "task-management",
    "recurring-invoices",
    "e-invoicing-es",
)
DUPLICATE_CHECK_SKILLS = (
    "purchase_invoice_from_pdf.md",
    "quotation_to_order.md",
    "party_by_nif.md",
    "delivery_note_create.md",
    "payment_entry.md",
)


def _manifest():
    with open(os.path.join(APP, "data", "system_skills.json"), encoding="utf-8") as f:
        return json.load(f)


def _read(name):
    with open(os.path.join(DOCS, name), encoding="utf-8") as f:
        return f.read()


class TestSystemSkillsContent(unittest.TestCase):
    def test_manifest_ids_unique_and_files_exist(self):
        skills = _manifest()
        ids = [s["skill_id"] for s in skills]
        self.assertEqual(len(ids), len(set(ids)))
        for s in skills:
            self.assertTrue(os.path.exists(os.path.join(DOCS, s["content_file"])), s["skill_id"])

    def test_new_spanish_skills_are_registered(self):
        ids = {s["skill_id"] for s in _manifest()}
        for skill_id in NEW_SKILLS:
            self.assertIn(skill_id, ids)

    def test_new_skills_only_reference_existing_tools(self):
        from pibiassistant.utils.plugin_manager import get_plugin_manager

        tools = set(get_plugin_manager().get_all_tools())
        import re

        by_id = {s["skill_id"]: s for s in _manifest()}
        for skill_id in NEW_SKILLS:
            text = _read(by_id[skill_id]["content_file"])
            for tool in set(re.findall(r"`([a-z_]+)`", text)):
                if tool in {"list_documents", "get_document", "search_documents", "create_document",
                            "update_document", "submit_document", "delete_document", "aggregate_documents",
                            "get_doctype_info", "generate_report", "send_email", "extract_file_content",
                            "attach_file"}:
                    self.assertIn(tool, tools, f"{skill_id} -> {tool}")

    def test_duplicate_checks_pass_docstatus_and_forbid_deleting_submitted(self):
        for name in DUPLICATE_CHECK_SKILLS:
            text = _read(name)
            self.assertIn("docstatus: [0, 1]", text, name)
            self.assertIn("delete_document", text, name)
