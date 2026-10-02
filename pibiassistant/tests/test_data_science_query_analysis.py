# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""run_database_query / analyze_business_data: pandas analysis, row caps, permissions."""

import frappe

from pibiassistant.plugins.data_science.tools.analyze_business_data import AnalyzeFrappeData
from pibiassistant.plugins.data_science.tools.run_database_query import QueryAndAnalyse
from pibiassistant.plugins.limits import clamp_int, clamp_limit
from pibiassistant.tests.base_test import BaseAssistantTest


class TestRunDatabaseQuery(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.tool = QueryAndAnalyse()

    def _run(self, **args):
        args.setdefault("query", "SELECT name, creation FROM `tabVersion`")
        return self.tool.execute(args)

    def test_statistical_analysis_survives_frappe_dict_rows(self):
        result = self._run(query="SELECT name, idx FROM `tabUser`", analysis_type="statistical")
        self.assertTrue(result["success"], result)
        self.assertNotIn("error", result["analysis"], result["analysis"])
        self.assertIn("basic_info", result["analysis"])

    def test_user_limit_clause_cannot_exceed_cap(self):
        result = self._run(query="SELECT name FROM `tabVersion` LIMIT 100000", limit=2)
        self.assertTrue(result["success"], result)
        self.assertLessEqual(result["rows_returned"], 2)

    def test_limit_text_in_comment_does_not_disable_cap(self):
        result = self._run(query="SELECT name FROM `tabVersion` -- no limit here", limit=1)
        self.assertTrue(result["success"], result)
        self.assertLessEqual(result["rows_returned"], 1)

    def test_zero_and_negative_limits_are_clamped(self):
        for bad in (0, -1, "abc"):
            result = self._run(limit=bad)
            self.assertTrue(result["success"], (bad, result))
            self.assertLessEqual(result["rows_returned"], 100)

    def test_duplicate_column_join_still_runs_and_is_capped(self):
        query = "SELECT a.name, b.name FROM `tabRole` a JOIN `tabRole` b ON a.name = b.name"
        result = self._run(query=query, limit=3)
        self.assertTrue(result["success"], result)
        self.assertLessEqual(result["rows_returned"], 3)

    def test_clamp_helpers(self):
        self.assertEqual(clamp_limit(10**6, 20, 1000), 1000)
        self.assertEqual(clamp_limit(0), 20)
        self.assertEqual(clamp_limit(None, 20, 1000), 20)
        self.assertEqual(clamp_int("x", 5, 1, 9), 5)


class TestAnalyzeBusinessData(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.tool = AnalyzeFrappeData()

    def test_default_fields_are_real_columns(self):
        # Sales Invoice has virtual/non-column fields that made the default select fail.
        result = self.tool.execute({"doctype": "Sales Invoice", "analysis_type": "profile", "limit": 50})
        if not result["success"]:
            self.assertIn("No data found", result["error"])
        else:
            self.assertGreater(result["record_count"], 0)

    def test_correlations_are_json_safe_and_capped(self):
        import json

        result = self.tool.execute({"doctype": "Sales Invoice", "analysis_type": "correlations", "limit": 200})
        if result["success"] and "correlation_matrix" in result["analysis_result"]:
            json.dumps(result["analysis_result"], allow_nan=False, default=float)
            self.assertLessEqual(len(result["analysis_result"]["numeric_fields"]), 15)
            self.assertLessEqual(len(result["analysis_result"]["strong_correlations"]), 20)

    def test_restricted_user_gets_permission_filtered_rows(self):
        email = "zz-analyze-o3@example.com"
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "ZZ Analyze",
                "send_welcome_email": 0,
                "roles": [{"role": "Sales User"}],
            }
        ).insert(ignore_permissions=True)
        todo = frappe.get_doc({"doctype": "ToDo", "description": "ZZ analyze o3"}).insert(
            ignore_permissions=True
        )
        try:
            frappe.set_user(email)
            with self.enforce_only_for_checks():
                result = self.tool.execute({"doctype": "ToDo", "analysis_type": "profile"})
            self.assertFalse(result["success"], result)
        finally:
            frappe.set_user("Administrator")
            frappe.delete_doc("ToDo", todo.name, force=True, ignore_permissions=True)
            frappe.delete_doc("User", user.name, force=True, ignore_permissions=True)
