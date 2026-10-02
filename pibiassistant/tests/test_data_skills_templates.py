"""Seed data consistency: every skill file exists and Spanish skills have a '/' template."""

import json
import os
import unittest

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(os.path.dirname(APP), "docs", "skills")

NEEDS_TEMPLATE = (
    "bank-reconciliation",
    "journal-entry-month-close",
    "item-creation",
    "manufacturing-work-order",
    "issue-followup",
    "task-management",
    "recurring-invoices",
    "e-invoicing-es",
    "sales-analysis-es",
    "financial-statements-es",
    "tax-models-es",
)


def _load(name):
    with open(os.path.join(APP, "data", name), encoding="utf-8") as fh:
        return json.load(fh)


class TestSeedData(unittest.TestCase):
    def test_skill_content_files_exist_and_ids_unique(self):
        skills = _load("system_skills.json")
        ids = [s["skill_id"] for s in skills]
        self.assertEqual(len(ids), len(set(ids)))
        for skill in skills:
            self.assertTrue(os.path.isfile(os.path.join(DOCS, skill["content_file"])), skill["skill_id"])

    def test_new_tax_skills_are_registered(self):
        ids = {s["skill_id"] for s in _load("system_skills.json")}
        self.assertLessEqual({"spanish-tax-lines-es", "tax-models-es"}, ids)

    def test_each_listed_skill_has_a_template_that_references_it(self):
        templates = _load("system_prompt_templates.json")
        prompt_ids = [t["prompt_id"] for t in templates]
        self.assertEqual(len(prompt_ids), len(set(prompt_ids)))
        for skill_id in NEEDS_TEMPLATE:
            self.assertTrue(
                any(f"skill {skill_id} (get_skill)" in t["template_content"] for t in templates), skill_id
            )

    def test_template_arguments_are_declared_in_the_body(self):
        for t in _load("system_prompt_templates.json"):
            for arg in t.get("arguments", []):
                self.assertIn(arg["argument_name"], t["template_content"], t["prompt_id"])

    def test_skill_docs_do_not_promise_a_cancel_tool(self):
        for name in ("update_document.md", "delete_document.md"):
            with open(os.path.join(DOCS, name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn("run_workflow` to amend/cancel", text)
            self.assertNotIn("Cancel before deleting", text)
