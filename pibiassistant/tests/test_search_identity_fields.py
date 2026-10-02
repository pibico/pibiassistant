"""search_documents identity fields, LIKE escaping, paging and client-error messages. Rolls back; no commits."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe

try:
    from frappe.tests import IntegrationTestCase
except ImportError:
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from pibiassistant.plugins.core.tools.list_documents import DocumentList
from pibiassistant.plugins.core.tools.search_tools import (
    SearchTools,
    escape_like,
    normalise_tax_id,
    resolve_search_fields,
)

PLUGINS = Path(__file__).resolve().parents[1] / "plugins"


class TestSearchIdentityFields(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.db.rollback()

    def _supplier(self):
        doc = frappe.get_doc(
            {"doctype": "Supplier", "supplier_name": "ZZ Tax Test SL", "supplier_group": frappe.db.get_value("Supplier Group", {}, "name"), "tax_id": "B87625489"}
        ).insert()
        return doc.name

    def test_identity_fields_are_searchable(self):
        fields = resolve_search_fields(frappe.get_meta("Supplier"))
        self.assertIn("tax_id", fields)

    def test_search_by_tax_id_plain_and_with_separators(self):
        name = self._supplier()
        for q in ("B87625489", "b-876.25489"):
            res = SearchTools.search_doctype("Supplier", q)
            self.assertTrue(res["success"], res)
            self.assertIn(name, [r["name"] for r in res["results"]], q)

    def test_like_wildcards_are_literal(self):
        self._supplier()
        self.assertEqual(SearchTools.search_doctype("Supplier", "%")["count"], 0)
        self.assertEqual(escape_like("a%b_c"), "a\\%b\\_c")
        self.assertEqual(normalise_tax_id("b-876 25.489"), "B87625489")

    def test_start_pages_without_overlap(self):
        for i in range(4):
            frappe.get_doc({"doctype": "ToDo", "description": f"ZZ-PAGE {i}"}).insert()
        flt = {"description": ["like", "ZZ-PAGE%"]}
        tool = DocumentList()
        first = tool.execute({"doctype": "ToDo", "filters": flt, "fields": ["name"], "limit": 2, "order_by": "name asc"})
        second = tool.execute({"doctype": "ToDo", "filters": flt, "fields": ["name"], "limit": 2, "start": 2, "order_by": "name asc"})
        self.assertTrue(first["has_more"])
        self.assertEqual(first["next_start"], 2)
        a = {d["name"] for d in first["data"]}
        b = {d["name"] for d in second["data"]}
        self.assertEqual(len(b), 2)
        self.assertFalse(a & b)
        self.assertFalse(second["has_more"])
        self.assertNotIn("next_start", second)

    def test_bad_field_is_friendly_and_not_logged(self):
        before = frappe.db.count("Error Log")
        res = DocumentList().execute({"doctype": "ToDo", "filters": {"no_such_field_zz": "x"}})
        self.assertFalse(res["success"])
        self.assertNotIn("SELECT", res["error"])
        self.assertEqual(frappe.db.count("Error Log"), before)

    def test_chatgpt_fetch_missing_doc_is_not_found_and_not_logged(self):
        from pibiassistant.plugins.core.tools.chatgpt_fetch import ChatGPTFetch

        before = frappe.db.count("Error Log")
        with self.assertRaises(frappe.DoesNotExistError) as cm:
            ChatGPTFetch().execute({"id": "ToDo/ZZ-does-not-exist"})
        self.assertIn("not found", str(cm.exception).lower())
        self.assertEqual(frappe.db.count("Error Log"), before)


class TestPaoFixes(IntegrationTestCase):
    def test_wkhtmltopdf_fallback_is_reached(self):
        from pibiassistant.plugins.pao.tools.generate_document import GenerateDocument

        tool = GenerateDocument.__new__(GenerateDocument)
        tool.logger = MagicMock()
        with patch.dict("sys.modules", {"weasyprint": None}), patch(
            "frappe.utils.pdf.get_pdf", return_value=b"%PDF"
        ) as get_pdf:
            self.assertEqual(tool._generate_pdf("<p>x</p>", "A4", "portrait"), b"%PDF")
        get_pdf.assert_called_once()

    def test_suggestions_name_existing_tools(self):
        for path in PLUGINS.rglob("*.py"):
            text = path.read_text()
            self.assertIsNone(re.search(r"document_(get|update|list)\b(?! =)", text.replace("document_get = ", "").replace("document_update = ", "").replace("document_list = ", "")), path)
