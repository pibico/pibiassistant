import json
import os
import re

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest

APP_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
SKILLS_DIR = os.path.join(os.path.dirname(APP_DIR), "docs", "skills")

TOOL_LIKE = re.compile(
    r"\b(?:run|list|get|create|update|delete|submit|search|generate|extract|attach|send|aggregate|analyze|browser|report)_[a-z_]+\b"
)
# Identifiers that look like tools but are parameters, fields or API names.
NOT_TOOLS = {
    "submit_on_creation",
    "get_doc",
    "get_all",
    "get_value",
    "get_list",
    "get_cached_doc",
    "get_roles",
    "get_url",
    "report_type",
    "report_name",
    "report_date",
    "search_fields",
    "search_field",
    "create_new",
    "create_doc",
    "list_view",
    "run_method",
    "send_email_alert",
    "send_notification",
    "update_stock",
    "update_modified",
    "generate_hash",
    "send_as_html",
    "aggregate_function",
    "extract_tables",
    "get_documents",
    "get_first_day",
    "get_last_day",
    "get_report_info",
    "list_reports",
    "search_doctype",
    "search_link",
    "search_mode",
}


def all_tool_names():
    from pibiassistant.utils.plugin_manager import get_plugin_manager

    manager = get_plugin_manager()
    names = set()
    for plugin_name, info in manager._discovered_plugins.items():
        names.update(manager._load_plugin_tools(plugin_name, info))
    return names


def load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


class TestShippedToolNames(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tools = all_tool_names()

    def _unknown(self, text):
        return sorted(set(TOOL_LIKE.findall(text)) - self.tools - NOT_TOOLS)

    def test_registry_is_not_empty(self):
        self.assertGreater(len(self.tools), 20)

    def test_prompt_templates_name_only_existing_tools(self):
        for prompt in load("system_prompt_templates.json"):
            self.assertEqual(
                self._unknown(prompt["template_content"]), [], f"unknown tools in prompt {prompt['prompt_id']}"
            )

    def test_prompt_ids_are_unique(self):
        ids = [p["prompt_id"] for p in load("system_prompt_templates.json")]
        self.assertEqual(len(ids), len(set(ids)))

    def test_prompt_arguments_are_used_and_declared(self):
        for prompt in load("system_prompt_templates.json"):
            declared = {a["argument_name"] for a in prompt["arguments"]}
            used = set(re.findall(r"\{\{\s*([a-z_]+)\s*\}\}", prompt["template_content"]))
            self.assertLessEqual(used, declared, f"{prompt['prompt_id']} uses undeclared arguments")

    def test_skill_documents_name_only_existing_tools(self):
        for skill in load("system_skills.json"):
            path = os.path.join(SKILLS_DIR, skill["content_file"])
            with open(path, encoding="utf-8") as f:
                self.assertEqual(self._unknown(f.read()), [], f"unknown tools in {skill['content_file']}")


class TestSystemSkillsManifest(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tools = all_tool_names()
        cls.skills = load("system_skills.json")

    def test_required_fields_and_unique_ids(self):
        ids = [s["skill_id"] for s in self.skills]
        self.assertEqual(len(ids), len(set(ids)))
        for skill in self.skills:
            for field in ("skill_id", "title", "description", "skill_type", "content_file"):
                self.assertTrue(skill.get(field), f"{skill.get('skill_id')} lacks {field}")
            self.assertIn(skill["skill_type"], ("Tool Usage", "Workflow"))
            self.assertTrue(os.path.exists(os.path.join(SKILLS_DIR, skill["content_file"])), skill["content_file"])

    def test_linked_tools_exist(self):
        for skill in self.skills:
            if skill.get("linked_tool"):
                self.assertIn(skill["linked_tool"], self.tools, skill["skill_id"])

    def test_business_workflow_skills_present_in_spanish(self):
        ids = {s["skill_id"] for s in self.skills}
        for needed in (
            "purchase-invoice-from-pdf",
            "sales-invoice-create",
            "quotation-to-order",
            "party-by-nif",
            "timesheet-entry",
            "stock-levels",
            "receivables-aging",
            "vat-summary-es",
            "crm-pipeline",
            "project-status",
            "attach-file-usage",
            "create-upload-link-usage",
            "send-email-usage",
            "browser-tools-usage",
        ):
            self.assertIn(needed, ids)

    def test_every_registered_core_tool_is_covered_by_a_skill(self):
        linked = {s.get("linked_tool") for s in self.skills}
        for tool in ("attach_file", "create_upload_link", "send_email", "aggregate_documents", "get_pending_approvals"):
            self.assertIn(tool, linked)
