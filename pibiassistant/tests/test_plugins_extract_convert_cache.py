"""extract_file_content caches AIDA conversions per File version."""

from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.plugins.data_science.tools.extract_file_content import ExtractFileContent
from pibiassistant.tests.base_test import BaseAssistantTest

CONVERT = "pibiassistant.pibiassistant_chat.api.aida.convert_bytes_to_markdown"


class TestConvertCache(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.tool = ExtractFileContent()
        self.file = MagicMock(file_name="zz.pdf", file_size=10, file_url="/files/zz.pdf", modified="v1")
        self.file.name = "ZZ-FILE-CACHE-%s" % frappe.generate_hash(length=6)

    def _run(self, convert):
        with patch.object(self.tool, "_get_file_document", return_value=self.file), patch.object(
            self.tool, "_get_file_content", return_value=b"x"
        ), patch(CONVERT, convert):
            return self.tool.execute({"file_url": "/files/zz.pdf"})

    def tearDown(self):
        for op in ("extract", "ocr"):
            for v in ("v1", "v2"):
                frappe.cache().delete_value(f"pa_convert:{self.file.name}:{v}:{op}")
        super().tearDown()

    def test_second_execute_hits_cache(self):
        convert = MagicMock(return_value=("# Hello", None))
        first, second = self._run(convert), self._run(convert)
        self.assertEqual(convert.call_count, 1)
        self.assertEqual(first["content"], second["content"])
        self.assertEqual(second["extraction_method"], "aida_convert")

    def test_modified_file_invalidates(self):
        convert = MagicMock(return_value=("# Hello", None))
        self._run(convert)
        self.file.modified = "v2"
        self._run(convert)
        self.assertEqual(convert.call_count, 2)

    def test_errors_and_oversize_are_not_cached(self):
        failing = MagicMock(return_value=("", "boom"))
        with patch.object(self.tool, "_get_file_content", return_value=b"x"), patch(CONVERT, failing), patch(
            "pibiassistant.plugins.data_science.tools.extract_file_content.frappe.log_error"
        ):
            self.assertIsNone(self.tool._try_convert_api({"operation": "extract"}, self.file))
            self.assertIsNone(self.tool._try_convert_api({"operation": "extract"}, self.file))
        self.assertEqual(failing.call_count, 2)
        big = MagicMock(return_value=("a" * (ExtractFileContent.CONVERT_CACHE_MAX_CHARS + 1), None))
        self._run(big)
        self._run(big)
        self.assertEqual(big.call_count, 2)
