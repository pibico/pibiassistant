"""Filter shapes models send must mean what they say: "between" with two loose values or a bare year used
to match nothing, so totals came back empty with success=true."""

import unittest

from pibiassistant.plugins.core.tools.list_documents import normalize_filter_shapes

DATE = lambda f: "Date" if f == "posting_date" else "Data"


class TestFilterShapes(unittest.TestCase):
    def fix(self, filters):
        return normalize_filter_shapes("Sales Invoice", filters, DATE)

    def test_between_with_two_loose_values(self):
        self.assertEqual(self.fix({"posting_date": ["between", "2026-01-01", "2026-12-31"]}), {"posting_date": ["between", ["2026-01-01", "2026-12-31"]]})

    def test_correct_between_is_untouched(self):
        f = {"posting_date": ["between", ["2026-01-01", "2026-12-31"]], "customer": "ACME"}
        self.assertEqual(self.fix(f), f)

    def test_in_with_loose_values(self):
        self.assertEqual(self.fix({"status": ["in", "Paid", "Unpaid"]}), {"status": ["in", ["Paid", "Unpaid"]]})
        self.assertEqual(self.fix({"status": ["in", ["Paid"]]}), {"status": ["in", ["Paid"]]})

    def test_year_and_month_on_a_date_field(self):
        self.assertEqual(self.fix({"posting_date": "2026"}), {"posting_date": ["between", ["2026-01-01", "2026-12-31"]]})
        self.assertEqual(self.fix({"posting_date": "2024-02"}), {"posting_date": ["between", ["2024-02-01", "2024-02-29"]]})

    def test_year_on_a_non_date_field_stays(self):
        self.assertEqual(self.fix({"customer": "2026"}), {"customer": "2026"})

    def test_list_form_between(self):
        self.assertEqual(self.fix([["posting_date", "between", "2026-01-01", "2026-12-31"]]), [["posting_date", "between", ["2026-01-01", "2026-12-31"]]])

    def test_list_form_year_equality(self):
        self.assertEqual(self.fix([["posting_date", "=", "2026"]]), [["posting_date", "between", ["2026-01-01", "2026-12-31"]]])

    def test_empty_and_other_shapes(self):
        self.assertEqual(self.fix({}), {})
        self.assertIsNone(self.fix(None))
