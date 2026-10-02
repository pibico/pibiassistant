"""run_python_code must not rewrite user code with regexes (list indexing, string literals)."""

from pibiassistant.plugins.data_science.tools.run_python_code import ExecutePythonCode
from pibiassistant.tests.base_test import BaseAssistantTest


class TestPreprocess(BaseAssistantTest):
    def _pre(self, code):
        return ExecutePythonCode.__new__(ExecutePythonCode)._preprocess_code_for_common_errors(code)

    def test_list_indexing_untouched(self):
        code = "data = [10, 20, 30]\nfirst = data[0]\nprint(first)"
        self.assertEqual(self._pre(code)["code"], code)

    def test_string_literal_untouched(self):
        code = "text = 'a = data[0] is shown'\nprint(text)"
        self.assertEqual(self._pre(code)["code"], code)

    def test_dataframe_slice_untouched_and_inplace_kept(self):
        code = "df2 = df[df.x > 1]\ndf.sort_values('x', inplace=True)"
        result = self._pre(code)
        self.assertEqual(result["code"], code)
        self.assertEqual(result["fixes_applied"], [])

    def test_concat_default_still_applied(self):
        out = self._pre("r = pd.concat([a, b])")
        self.assertIn("ignore_index=True", out["code"])

    def test_list_indexing_and_string_execute_unchanged(self):
        result = ExecutePythonCode().execute(
            {"code": "data = [10, 20, 30]\nfirst = data[0]\ntext = 'a = data[0] is shown'\nprint(first, text)"}
        )
        self.assertTrue(result["success"], result)
        self.assertEqual(result["output"].strip(), "10 a = data[0] is shown")
