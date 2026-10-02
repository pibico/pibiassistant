import frappe

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.tests.base_test import BaseAssistantTest


class _SchemaTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "zz_schema_tool"
        self.description = "Schema validation fixture"
        self.inputSchema = {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["line", "bar"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                "ratio": {"type": "number"},
                "name": {"type": "string", "minLength": 2},
                "either": {"type": ["string", "null"]},
            },
            "required": [],
        }

    def execute(self, arguments):
        return arguments


class TestArgumentValidation(BaseAssistantTest):
    def setUp(self):
        self.tool = _SchemaTool()

    def _invalid(self, arguments):
        with self.assertRaises(frappe.ValidationError):
            self.tool.validate_arguments(arguments)

    def test_valid_arguments_pass(self):
        self.tool.validate_arguments({"kind": "bar", "limit": 5, "ratio": 1, "name": "ab", "either": None})

    def test_unknown_argument_is_rejected_with_valid_names(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self.tool.validate_arguments({"functions": ["count"]})
        self.assertIn("functions", str(ctx.exception))
        self.assertIn("limit", str(ctx.exception))

    def test_unknown_argument_allowed_when_schema_is_open(self):
        self.tool.inputSchema = {**self.tool.inputSchema, "additionalProperties": True}
        self.tool.validate_arguments({"extra": 1})

    def test_enum_is_enforced(self):
        self._invalid({"kind": "Bogus"})

    def test_bounds_are_enforced(self):
        self._invalid({"limit": 0})
        self._invalid({"limit": 101})

    def test_min_length_is_enforced(self):
        self._invalid({"name": "a"})

    def test_bool_is_not_a_number(self):
        self._invalid({"limit": True})
        self._invalid({"ratio": False})

    def test_union_types(self):
        self.tool.validate_arguments({"either": "x"})
        self._invalid({"either": 3})
