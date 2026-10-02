import os
import re
import unittest

import frappe

from pibiassistant.tests.test_data_skills_content import DOCS, _manifest, _read

READ_ONLY_SKILLS = ("sales-analysis-es", "financial-statements-es")


class TestSkillsRespectToolRestrictions(unittest.TestCase):
    def test_aggregate_documents_never_targets_child_or_single_doctypes(self):
        for name in sorted(os.listdir(DOCS)):
            for line in _read(name).splitlines():
                if "aggregate_documents" not in line:
                    continue
                for dt in re.findall(r"`([A-Z][A-Za-z ]+)`", line):
                    row = frappe.db.get_value("DocType", dt, ["istable", "issingle"], as_dict=True)
                    if row and (row.istable or row.issingle):
                        # a sentence that warns against the doctype is fine
                        self.assertRegex(line, r"(no se puede|no la agrega|no intentes|rechaza)", f"{name}: {dt}")

    def test_sales_and_financial_skills_registered_and_read_only(self):
        from pibiassistant.pibiassistant_chat.api.chat.aida_tools import READ_TOOLS

        by_id = {s["skill_id"]: s for s in _manifest()}
        for skill_id in READ_ONLY_SKILLS:
            self.assertIn(skill_id, by_id)
            text = _read(by_id[skill_id]["content_file"])
            used = set(re.findall(r"`([a-z_]+)`", text)) & {
                "list_documents", "get_document", "search_documents", "create_document", "update_document",
                "submit_document", "delete_document", "send_email", "run_workflow", "generate_document",
                "attach_file", "aggregate_documents", "generate_report", "report_list", "report_requirements",
                "get_doctype_info",
            }
            self.assertTrue(used, skill_id)
            self.assertTrue(used <= READ_TOOLS, f"{skill_id}: {used - READ_TOOLS}")
