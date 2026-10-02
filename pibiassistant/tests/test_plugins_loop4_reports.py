"""generate_report: empty prepared results, checkbox defaults and error logging."""

from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.plugins.core.tools.report_tools import ReportTools
from pibiassistant.plugins.query_errors import log_failure
from pibiassistant.tests.base_test import BaseAssistantTest

PREPARED = "frappe.core.doctype.prepared_report.prepared_report"


class TestPreparedReportEmptyResult(BaseAssistantTest):
    def _report(self):
        report = MagicMock()
        report.name = "ZZ Report"
        return report

    def test_cached_empty_result_is_returned(self):
        prepared = MagicMock(modified="2026-01-01")
        empty = {"result": [], "columns": [{"fieldname": "a"}], "doc": prepared, "prepared_report": True}
        with patch(f"{PREPARED}.get_completed_prepared_report", return_value="PR-1"), patch(
            "frappe.desk.query_report.get_prepared_report_result", return_value=empty
        ):
            out = ReportTools._handle_prepared_report_execution(self._report(), {})
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["result"], [])
        self.assertEqual(out["source"], "cached")
        self.assertIn("no rows", out["message"])

    def test_completed_empty_result_returns_within_one_poll(self):
        empty = {"result": [], "columns": [], "prepared_report": True, "doc": None}
        doc = MagicMock(status="Completed")
        with patch(f"{PREPARED}.get_completed_prepared_report", return_value=None), patch(
            f"{PREPARED}.make_prepared_report", return_value={"name": "PR-2"}
        ), patch("frappe.desk.query_report.get_prepared_report_result", return_value=empty), patch(
            "frappe.get_value", return_value=120
        ), patch("frappe.get_doc", return_value=doc), patch("frappe.db.commit"), patch(
            "frappe.db.rollback"
        ), patch("time.sleep") as sleep:
            out = ReportTools._handle_prepared_report_execution(self._report(), {})
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["source"], "background_job_completed")
        self.assertEqual(sleep.call_count, 1)


class TestCheckboxDefaults(BaseAssistantTest):
    def test_string_zero_default_becomes_int_zero(self):
        defs = {"include_payments": {"fieldtype": "Check", "default": "0"}, "company": {"fieldtype": "Link", "default": "X"}}
        out = ReportTools._apply_filter_defaults(MagicMock(), {}, defs)
        self.assertEqual(out["include_payments"], 0)
        self.assertEqual(out["company"], "X")

    def test_missing_checkbox_without_default_is_zero_and_caller_value_kept(self):
        defs = {"a": {"fieldtype": "Check"}, "b": {"fieldtype": "Check", "default": 0}}
        out = ReportTools._apply_filter_defaults(MagicMock(), {"b": "1"}, defs)
        self.assertEqual((out["a"], out["b"]), (0, 1))
        out = ReportTools._apply_filter_defaults(MagicMock(), {"a": "false"}, defs)
        self.assertEqual(out["a"], 0)

    def test_sales_register_runs_with_defaults(self):
        if not frappe.db.exists("Report", "Sales Register"):
            self.skipTest("Sales Register report not installed")
        result = ReportTools.execute_report("Sales Register", {})
        self.assertTrue(result["success"], result)


class TestErrorLogging(BaseAssistantTest):
    def test_user_errors_are_not_logged_and_titles_are_short(self):
        before = frappe.db.count("Error Log")
        log_failure("T", frappe.ValidationError("x"))
        log_failure("T", frappe.PermissionError("x"))
        self.assertEqual(frappe.db.count("Error Log"), before)
        log_failure("T" * 300, RuntimeError("e" * 500))
        self.assertEqual(frappe.db.count("Error Log"), before + 1)
        row = frappe.get_all("Error Log", fields=["method", "error"], order_by="creation desc", limit=1)[0]
        self.assertLessEqual(len(row.method or ""), 140)

    def test_long_exception_returns_error_dict(self):
        with patch("frappe.db.exists", side_effect=RuntimeError("e" * 5000)):
            out = ReportTools.execute_report("ZZ", {})
        self.assertFalse(out["success"])
        self.assertLessEqual(len(out["error"]), 2000)

    def test_missing_mandatory_filters_do_not_log(self):
        before = frappe.db.count("Error Log")
        err = frappe.MandatoryError("Please select a customer")
        with patch("frappe.db.exists", side_effect=err):
            out = ReportTools.execute_report("ZZ", {})
        self.assertFalse(out["success"])
        self.assertEqual(frappe.db.count("Error Log"), before)
