import json
import os
import re
import unittest

import frappe

DATA = os.path.join(frappe.get_app_path("pibiassistant"), "data")
NEW_SKILLS = (
    "purchase-order-receipt",
    "delivery-note-create",
    "payment-entry",
    "supplier-payables",
    "expense-claim",
    "credit-note-es",
    "lead-opportunity",
)


def _load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


class TestPromptSkillReferences(unittest.TestCase):
    def test_prompts_reference_existing_skills(self):
        skills = {s["skill_id"] for s in _load("system_skills.json")}
        for prompt in _load("system_prompt_templates.json"):
            for skill_id in re.findall(r"skill ([a-z0-9-]+) \(get_skill\)", prompt["template_content"]):
                self.assertIn(skill_id, skills, f"{prompt['prompt_id']} -> {skill_id}")

    def test_new_sme_flows_have_skill_and_prompt(self):
        skills = {s["skill_id"] for s in _load("system_skills.json")}
        used = " ".join(p["template_content"] for p in _load("system_prompt_templates.json"))
        for skill_id in NEW_SKILLS:
            self.assertIn(skill_id, skills)
            self.assertIn(f"skill {skill_id} (get_skill)", used)
