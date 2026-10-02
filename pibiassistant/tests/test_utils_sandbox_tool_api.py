
from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.utils import code_execution_subprocess, tool_api


class TestSandboxToolAPI(BaseAssistantTest):
    def test_renamed_class_is_importable_and_no_legacy_alias_remains(self):
        self.assertTrue(hasattr(tool_api, "SandboxToolAPI"))
        self.assertFalse(hasattr(tool_api, "FrappeAssistantAPI"))
        self.assertIn("SandboxToolAPI", open(code_execution_subprocess.__file__).read())

    def test_get_document_goes_through_permission_checks(self):
        api = tool_api.SandboxToolAPI("Administrator")
        result = api.get_document("User", "Administrator")
        self.assertIsInstance(result, dict)
