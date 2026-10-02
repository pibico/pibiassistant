import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import frappe

from pibiassistant.api.handlers import prompts
from pibiassistant.api.handlers.prompts import PromptTemplateManager, handle_prompts_get


def _doc(engine, template, regex=""):
    return NS(
        template_content=template,
        rendering_engine=engine,
        description="d",
        arguments=[
            NS(argument_name="x", argument_type="string", is_required=0, default_value="",
               validation_regex=regex, allowed_values="")
        ],
    )


class TestPromptsGetRenderErrors(unittest.TestCase):
    def _get(self, doc, arguments=None, get_value=None):
        calls = get_value or (lambda *a, **k: "ZZ-P")
        with patch.object(frappe.db, "get_value", side_effect=calls), \
             patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(prompts, "user_can_access_shared_doc", return_value=True), \
             patch.object(prompts, "increment_usage"):
            return handle_prompts_get({"name": "zz-p", "arguments": arguments or {}}, 1)

    def test_format_string_error_is_invalid_params(self):
        res = self._get(_doc("Format String", "foo {bar"))
        self.assertEqual(res["error"]["code"], -32602)
        self.assertIn("zz-p", res["error"]["message"])

    def test_positional_format_index_error_is_invalid_params(self):
        res = self._get(_doc("Format String", "foo {0}"))
        self.assertEqual(res["error"]["code"], -32602)

    def test_bad_validation_regex_is_invalid_params(self):
        res = self._get(_doc("Jinja2", "hi", regex="(["), {"x": "a"})
        self.assertEqual(res["error"]["code"], -32602)

    def test_valid_prompt_still_renders(self):
        res = self._get(_doc("Raw", "hello"))
        self.assertEqual(res["result"]["messages"][0]["content"]["text"], "hello")

    def test_own_archived_prompt_is_found(self):
        seen = []

        def get_value(doctype, filters, fieldname):
            seen.append(filters["status"])
            return "ZZ-P" if filters["status"] == "Archived" else None

        res = self._get(_doc("Raw", "hello"), get_value=get_value)
        self.assertIn("result", res)
        self.assertEqual(seen[-1], "Archived")
