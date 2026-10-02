"""ReportTools._default_date_filters is shared by the script and query report executors."""

from unittest.mock import patch

import frappe
from frappe.utils import add_months, getdate

from pibiassistant.plugins.core.tools.report_tools import ReportTools
from pibiassistant.tests.base_test import BaseAssistantTest

FIX = "pibiassistant.plugins.core.tools.report_tools.frappe.db.get_value"


class TestReportFilterDefaults(BaseAssistantTest):
    def test_drops_none_and_non_dict(self):
        self.assertEqual(
            ReportTools._default_date_filters({"from_date": "2024-01-01", "to_date": "2024-02-01", "x": None}),
            {"from_date": "2024-01-01", "to_date": "2024-02-01"},
        )
        with patch(FIX, return_value=None):
            out = ReportTools._default_date_filters(None)
        self.assertEqual(out["to_date"], str(getdate()))

    def test_fiscal_year_fills_both_dates(self):
        with patch(FIX, return_value=("2024-01-01", "2024-12-31")):
            out = ReportTools._default_date_filters({})
        self.assertEqual((out["from_date"], out["to_date"]), ("2024-01-01", "2024-12-31"))

    def test_no_fiscal_year_falls_back_to_twelve_months(self):
        with patch(FIX, return_value=None):
            out = ReportTools._default_date_filters({})
        self.assertEqual(out["from_date"], str(add_months(getdate(), -12)))

    def test_fiscal_lookup_error_falls_back(self):
        with patch(FIX, side_effect=frappe.db.InternalError("x")):
            out = ReportTools._default_date_filters({})
        self.assertEqual(out["to_date"], str(getdate()))

    def test_single_bound_completed(self):
        self.assertEqual(ReportTools._default_date_filters({"from_date": "2024-03-01"})["to_date"], str(getdate()))
        self.assertEqual(
            ReportTools._default_date_filters({"to_date": "2024-03-01"})["from_date"], "2023-03-01"
        )
