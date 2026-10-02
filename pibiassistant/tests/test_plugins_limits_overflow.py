"""clamp_int must not raise for infinite floats; list/search tools fall back to their defaults."""

from unittest.mock import patch

from pibiassistant.plugins.core.tools.list_documents import DocumentList
from pibiassistant.plugins.core.tools.search_documents import SearchDocuments
from pibiassistant.plugins.limits import clamp_int, clamp_limit
from pibiassistant.tests.base_test import BaseAssistantTest


class TestLimitsOverflow(BaseAssistantTest):
    def test_clamp_int_special_values(self):
        self.assertEqual(clamp_int(float("inf"), 20, 1, 100), 20)
        self.assertEqual(clamp_int(float("-inf"), 20, 1, 100), 20)
        self.assertEqual(clamp_int("nan", 20, 1, 100), 20)
        self.assertEqual(clamp_int(float("nan"), 20, 1, 100), 20)
        self.assertEqual(clamp_int(None, 20, 1, 100), 20)
        self.assertEqual(clamp_int("7", 20, 1, 100), 7)
        self.assertEqual(clamp_limit(float("inf")), 20)

    def test_list_documents_accepts_infinite_limit(self):
        with patch("frappe.get_list", return_value=[]):
            result = DocumentList().execute({"doctype": "ToDo", "limit": float("inf")})
        self.assertTrue(result["success"], result)

    def test_search_documents_limit_rules(self):
        tool = SearchDocuments()
        self.assertEqual(tool._clamp_limit(float("inf")), 20)
        self.assertEqual(tool._clamp_limit(0), 20)
        self.assertEqual(tool._clamp_limit(-5), 20)
        self.assertEqual(tool._clamp_limit(1000), 100)
        self.assertEqual(tool._clamp_limit("5"), 5)
        self.assertEqual(tool._clamp_limit(None), 20)
