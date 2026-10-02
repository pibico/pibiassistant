"""Document tools: Single DocTypes, omitted fields, empty updates, periods, permission payloads, DB errors."""

from unittest.mock import patch

import frappe
from pymysql.err import OperationalError, ProgrammingError

from pibiassistant.plugins.core.tools.aggregate_documents import AggregateDocuments, period_label
from pibiassistant.plugins.core.tools.chatgpt_fetch import ChatGPTFetch
from pibiassistant.plugins.core.tools.list_documents import DocumentList, omitted_fields
from pibiassistant.plugins.core.tools.search_documents import SearchDocuments
from pibiassistant.plugins.core.tools.submit_document import DocumentSubmit
from pibiassistant.plugins.core.tools.update_document import DocumentUpdate
from pibiassistant.plugins.query_errors import (
    client_error_message,
    permission_error_result,
    single_doctype_message,
    strip_schema,
)
from pibiassistant.tests.base_test import BaseAssistantTest


class TestSingleDoctype(BaseAssistantTest):
    def test_list_and_search_point_to_get_document_without_logging(self):
        before = frappe.db.count("Error Log")
        listed = DocumentList().execute({"doctype": "System Settings"})
        searched = SearchDocuments().execute({"query": "x", "doctype": "System Settings"})
        for res in (listed, searched):
            self.assertFalse(res["success"])
            self.assertIn("get_document", res["error"])
        self.assertEqual(frappe.db.count("Error Log"), before)

    def test_regular_doctype_is_not_single(self):
        self.assertIsNone(single_doctype_message("ToDo"))
        self.assertIsNone(single_doctype_message("No Such DocType ZZ"))
        self.assertIsNone(single_doctype_message(None))


class TestOmittedFields(BaseAssistantTest):
    def test_helper(self):
        rows = [{"name": "a", "creation": 1}]
        self.assertEqual(omitted_fields(["name", "bogus", "count(name) as c"], rows), ["bogus"])
        self.assertEqual(omitted_fields(["bogus"], []), [])

    def test_list_reports_omitted_fields(self):
        with patch("frappe.get_list", return_value=[{"name": "T-1"}]):
            res = DocumentList().execute({"doctype": "ToDo", "fields": ["name", "bogus"], "limit": 1})
        self.assertTrue(res["success"], res)
        self.assertEqual(res["omitted_fields"], ["bogus"])
        self.assertIn("bogus", res["message"])

    def test_child_table_parent_comes_back(self):
        if not frappe.db.exists("Sales Taxes and Charges", {"parenttype": "Sales Invoice"}):
            self.skipTest("no tax rows on this site")
        res = DocumentList().execute(
            {
                "doctype": "Sales Taxes and Charges",
                "filters": {"parenttype": "Sales Invoice"},
                "fields": ["name", "parent", "parenttype"],
                "limit": 1,
            }
        )
        self.assertTrue(res["success"], res)
        self.assertIn("parent", res["data"][0])
        self.assertNotIn("omitted_fields", res)


class TestUpdateEmpty(BaseAssistantTest):
    def test_empty_data_is_rejected(self):
        for data in ({}, None, []):
            res = DocumentUpdate().execute({"doctype": "ToDo", "name": "x", "data": data})
            self.assertFalse(res["success"])
            self.assertEqual(res["error_type"], "empty_update")


class TestAggregatePeriod(BaseAssistantTest):
    def test_labels(self):
        self.assertEqual(period_label("month", 202503), "2025-03")
        self.assertEqual(period_label("quarter", 20253), "2025-Q3")
        self.assertEqual(period_label("year", 2025), 2025)
        self.assertIsNone(period_label("month", None))

    def test_period_needs_date_group(self):
        tool = AggregateDocuments()
        res = tool.execute({"doctype": "ToDo", "group_by": "status", "period": "month"})
        self.assertFalse(res["success"])
        res = tool.execute({"doctype": "ToDo", "period": "month"})
        self.assertFalse(res["success"])

    def test_period_query_shape_and_labels(self):
        rows = [{"pa_period": 202501, "count": 2}, {"pa_period": 202502, "count": 1}]
        with patch("frappe.get_list", return_value=rows) as get_list:
            res = AggregateDocuments().execute(
                {"doctype": "ToDo", "group_by": "creation", "period": "month", "limit": 12}
            )
        self.assertTrue(res["success"], res)
        kwargs = get_list.call_args.kwargs
        self.assertEqual(kwargs["group_by"], "`pa_period`")
        self.assertEqual(kwargs["order_by"], "`pa_period` asc")
        self.assertEqual(kwargs["limit"], 12)
        self.assertEqual([r["period"] for r in res["data"]], ["2025-01", "2025-02"])
        self.assertEqual(res["columns"], ["period", "count"])

    def test_period_group_still_honours_field_permission(self):
        with patch("frappe.get_list", return_value=[]):
            res = AggregateDocuments().execute({"doctype": "ToDo", "group_by": "modified_by", "period": "year"})
        self.assertFalse(res["success"])


class TestPermissionPayload(BaseAssistantTest):
    def test_shape_and_fallback(self):
        out = permission_error_result(frappe.PermissionError(""), "fallback", doctype="ToDo")
        self.assertEqual(out["error"], "fallback")
        self.assertEqual(out["error_type"], "permission_error")
        self.assertEqual(out["doctype"], "ToDo")
        self.assertEqual(permission_error_result(frappe.PermissionError("<b>No</b>"), "f")["error"], "No")


class TestDbErrorsAreGeneric(BaseAssistantTest):
    def test_driver_text_is_not_returned(self):
        leaks = (
            ProgrammingError(1064, "You have an error in your SQL syntax near 'between' at line 1"),
            OperationalError(1292, "Incorrect date value: '2025-02-31' for column `_abc123`.`tabToDo`.`date`"),
        )
        for exc in leaks:
            message = client_error_message(exc)
            self.assertTrue(message)
            self.assertNotIn("SQL", message)
            self.assertNotIn("_abc123", message)

    def test_strip_schema(self):
        schema = frappe.conf.db_name
        self.assertNotIn(schema, strip_schema(f"Table '{schema}.tabFoo' doesn't exist"))

    def test_list_documents_maps_db_error(self):
        with patch("frappe.get_list", side_effect=ProgrammingError(1064, "syntax near x")):
            res = DocumentList().execute({"doctype": "ToDo"})
        self.assertFalse(res["success"])
        self.assertNotIn("syntax", res["error"])


class TestFetchErrors(BaseAssistantTest):
    def test_bad_ids_raise_user_errors(self):
        before = frappe.db.count("Error Log")
        with self.assertRaises(frappe.ValidationError):
            ChatGPTFetch().execute({"id": "nope"})
        with self.assertRaises(frappe.ValidationError) as cm:
            ChatGPTFetch().execute({"id": "NoSuchDocType ZZ/abc"})
        self.assertIn("Unknown DocType", str(cm.exception))
        with self.assertRaises(frappe.DoesNotExistError):
            ChatGPTFetch().execute({"id": "ToDo/ZZ-none"})
        self.assertEqual(frappe.db.count("Error Log"), before)


class TestSubmitOrder(BaseAssistantTest):
    def test_missing_record_and_non_submittable_reported_before_permission(self):
        res = DocumentSubmit().execute({"doctype": "ToDo", "name": "ZZ-none"})
        self.assertFalse(res["success"])
        self.assertIn("not a submittable", res["error"])
        res = DocumentSubmit().execute({"doctype": "Sales Invoice", "name": "ZZ-none"})
        self.assertIn("not found", res["error"])
        res = DocumentSubmit().execute({"doctype": "No Such ZZ", "name": "x"})
        self.assertIn("not found", res["error"])
