import json
import os
from unittest.mock import patch

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.utils import migration_hooks

DATA = os.path.join(frappe.get_app_path("pibiassistant"), "data")


def _templates():
    with open(os.path.join(DATA, "system_prompt_templates.json"), encoding="utf-8") as f:
        return json.load(f)


def _skills():
    with open(os.path.join(DATA, "system_skills.json"), encoding="utf-8") as f:
        return json.load(f)


class TestSystemTemplateSync(BaseAssistantTest):
    def test_unchanged_manifest_saves_nothing_on_second_pass(self):
        withargs = next(t for t in _templates() if t.get("arguments"))
        migration_hooks._sync_system_prompt_template(withargs)
        with patch("frappe.model.document.Document.save") as save:
            self.assertEqual(migration_hooks._sync_system_prompt_template(withargs), "unchanged")
        save.assert_not_called()

    def test_changed_argument_is_detected(self):
        withargs = next(t for t in _templates() if t.get("arguments"))
        migration_hooks._sync_system_prompt_template(withargs)
        changed = {**withargs, "arguments": [{**withargs["arguments"][0], "description": "ZZ changed"}]}
        self.assertEqual(migration_hooks._sync_system_prompt_template(changed), "updated")

    def test_one_bad_template_does_not_stop_the_others(self):
        calls = []

        def fake(data):
            calls.append(data["prompt_id"])
            if len(calls) == 1:
                raise ValueError("bad")
            return "unchanged"

        with patch.object(migration_hooks, "_sync_system_prompt_template", side_effect=fake), patch(
            "frappe.db.commit"
        ), patch("frappe.log_error") as log_error:
            migration_hooks._install_system_prompt_templates()
        self.assertEqual(len(calls), len(_templates()))
        self.assertIn(calls[0], log_error.call_args.kwargs["message"])

    def test_one_bad_skill_does_not_stop_the_others(self):
        calls = []

        def fake(data, _dir):
            calls.append(data["skill_id"])
            if len(calls) == 1:
                raise ValueError("bad")
            return "unchanged"

        with patch.object(migration_hooks, "_sync_system_skill", side_effect=fake), patch(
            "frappe.db.commit"
        ), patch("frappe.log_error") as log_error:
            migration_hooks._install_system_skills()
        self.assertEqual(len(calls), len(_skills()))
        self.assertIn(calls[0], log_error.call_args.kwargs["message"])
