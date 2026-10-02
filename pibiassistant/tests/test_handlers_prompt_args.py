import unittest
from types import SimpleNamespace as NS

from pibiassistant.api.handlers.prompts import PromptTemplateManager


def _doc(engine="Jinja2", template="A{% if flag %}-FLAG{% endif %}{% if n %}-N{{ n }}{% endif %}"):
    return NS(
        template_content=template,
        rendering_engine=engine,
        arguments=[
            NS(argument_name="flag", argument_type="boolean", is_required=0, default_value="", validation_regex="", allowed_values=""),
            NS(argument_name="n", argument_type="number", is_required=0, default_value="", validation_regex="", allowed_values=""),
        ],
    )


class TestPromptArgumentCoercion(unittest.TestCase):
    def setUp(self):
        self.m = PromptTemplateManager()

    def test_false_like_booleans_hide_section(self):
        for value in ("false", "0", "False", False, 0):
            self.assertNotIn("FLAG", self.m.render_prompt(_doc(), {"flag": value}), repr(value))

    def test_true_like_booleans_show_section(self):
        for value in ("true", "1", "TRUE", True, 1):
            self.assertIn("FLAG", self.m.render_prompt(_doc(), {"flag": value}), repr(value))

    def test_zero_string_number_is_falsy_and_numbers_render(self):
        self.assertNotIn("-N", self.m.render_prompt(_doc(), {"n": "0"}))
        self.assertIn("-N5", self.m.render_prompt(_doc(), {"n": "5"}))
        self.assertIn("-N2.5", self.m.render_prompt(_doc(), {"n": "2.5"}))

    def test_defaults_are_coerced(self):
        doc = _doc()
        doc.arguments[0].default_value = "false"
        self.assertNotIn("FLAG", self.m.render_prompt(doc, {}))
        doc.arguments[0].default_value = "true"
        self.assertIn("FLAG", self.m.render_prompt(doc, {}))
