from types import SimpleNamespace as NS
from unittest.mock import patch

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.utils.permissions import increment_usage, user_can_access_shared_doc


def _doc(**kw):
    base = dict(owner_user="owner@example.com", visibility="Private", status="Draft", is_system=0, shared_with_roles=[])
    base.update(kw)
    return NS(**base)


class TestSharedDocAccessRule(BaseAssistantTest):
    def _can(self, doc, roles, user="u@example.com"):
        with patch.object(frappe, "get_roles", return_value=roles):
            return user_can_access_shared_doc(doc, user)

    def test_owner_and_system_manager(self):
        self.assertTrue(self._can(_doc(owner_user="u@example.com"), []))
        self.assertTrue(self._can(_doc(), ["System Manager"]))

    def test_private_and_draft_are_hidden(self):
        self.assertFalse(self._can(_doc(), ["Desk User"]))
        self.assertFalse(self._can(_doc(visibility="Public", status="Draft"), ["Desk User"]))

    def test_public_published(self):
        self.assertTrue(self._can(_doc(visibility="Public", status="Published"), []))

    def test_shared_requires_role_overlap(self):
        doc = _doc(visibility="Shared", status="Published", shared_with_roles=[NS(role="Sales User")])
        self.assertTrue(self._can(doc, ["Sales User"]))
        self.assertFalse(self._can(doc, ["HR User"]))

    def test_published_system_record(self):
        self.assertTrue(self._can(_doc(is_system=1, status="Published"), []))
        self.assertFalse(self._can(_doc(is_system=1, status="Draft"), []))

    def test_both_handlers_use_the_single_rule(self):
        from pibiassistant.api.handlers import prompts, resources

        self.assertIs(prompts.user_can_access_shared_doc, user_can_access_shared_doc)
        self.assertIs(resources.user_can_access_shared_doc, user_can_access_shared_doc)


class TestIncrementUsage(BaseAssistantTest):
    def test_rejects_unlisted_doctype(self):
        with self.assertRaises(ValueError):
            increment_usage("User", "Administrator")

    def test_bumps_skill_counter(self):
        name = frappe.db.get_value("PA Skill", {}, "name")
        if not name:
            self.skipTest("no PA Skill rows")
        before = frappe.db.get_value("PA Skill", name, "use_count") or 0
        increment_usage("PA Skill", name)
        self.assertEqual(frappe.db.get_value("PA Skill", name, "use_count"), before + 1)

    def test_bumps_prompt_counter(self):
        name = frappe.db.get_value("Prompt Template", {}, "name")
        if not name:
            self.skipTest("no Prompt Template rows")
        before = frappe.db.get_value("Prompt Template", name, "use_count") or 0
        increment_usage("Prompt Template", name)
        self.assertEqual(frappe.db.get_value("Prompt Template", name, "use_count"), before + 1)
