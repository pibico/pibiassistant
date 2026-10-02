# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""Generated documents must not use left accent bars (pibiCo UI guideline)."""

import inspect
import os
import unittest

from pibiassistant.plugins.pao.tools import rich_blocks


class TestPdfCalloutStyle(unittest.TestCase):
    def test_template_has_no_border_left(self):
        path = os.path.join(os.path.dirname(rich_blocks.__file__), "templates", "document_pdf.html")
        with open(path, encoding="utf-8") as fh:
            self.assertNotIn("border-left", fh.read())

    def test_rich_blocks_source_has_no_border_left(self):
        self.assertNotIn("border-left", inspect.getsource(rich_blocks))

    def test_callout_is_tinted_with_coloured_title(self):
        processed, tokens = rich_blocks.preprocess_rich_blocks(
            '```callout type="warning" title="Careful"\nbody\n```'
        )
        rendered = rich_blocks.restore_rich_blocks(processed, tokens)
        self.assertIn("background:#fffbeb", rendered)
        self.assertIn('class="callout-title" style="color:#92400e"', rendered)
        self.assertNotIn("border", rendered)
