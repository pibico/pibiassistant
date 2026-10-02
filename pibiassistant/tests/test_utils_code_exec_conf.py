"""The run_python_code sandbox must not reveal site secrets or server paths."""

import contextlib
import io

import frappe

from pibiassistant.plugins.data_science.tools.run_python_code import ExecutePythonCode
from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.utils import code_execution_subprocess as sandbox


def _secrets():
    return [str(v) for k, v in (frappe.conf or {}).items() if k in ("db_password", "encryption_key") and v]


class TestSandboxSecrets(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.env = sandbox._setup_execution_environment("Administrator")

    def _run(self, code):
        out = io.StringIO()
        sandbox._reject_private_attributes(code)
        with contextlib.redirect_stdout(out):
            exec(code, self.env)  # noqa: S102
        return out.getvalue()

    def test_conf_access_is_blocked(self):
        for code in (
            "frappe.conf",
            "frappe.get_conf()",
            "frappe.get_site_config()",
            "frappe.local.conf",
            "frappe.flags",
            "frappe.cache",
            "getattr(frappe, 'conf')",
            "frappe.utils.frappe",
            "db._original_db",
            "frappe.get_all.__globals__",
        ):
            with self.assertRaises((PermissionError, AttributeError), msg=code):
                self._run(code)

    def test_read_api_still_works(self):
        self.assertIn("Administrator", self._run("print(frappe.session.user)"))
        self.assertIn("1", self._run("print(len(frappe.get_all('User', limit=1)))"))
        self.assertIn("User", self._run("print(frappe.get_meta('User').name)"))
        self.assertTrue(self._run("print(frappe.utils.cint('3'))").strip() == "3")
        self.assertTrue(self._run("print(db.get_value('User', 'Administrator', 'name'))").strip())

    def test_tool_never_returns_secret_or_server_paths(self):
        secrets = _secrets()
        result = ExecutePythonCode().execute({"code": "print(frappe.conf.get('db_password'))"})
        blob = str(result)
        self.assertFalse(result.get("success"), result)
        for secret in secrets:
            self.assertNotIn(secret, blob)

    def test_private_attribute_hops_are_blocked_end_to_end(self):
        result = ExecutePythonCode().execute({"code": "print(frappe.get_all.__globals__.keys())"})
        self.assertFalse(result.get("success"), result)
        self.assertNotIn("conf", str(result.get("output")))

    def test_traceback_has_no_server_paths(self):
        result = ExecutePythonCode().execute({"code": "x = 1\nprint(1/0)"})
        self.assertFalse(result.get("success"), result)
        tb = result.get("traceback") or ""
        self.assertNotIn("/home/", tb)
        self.assertIn("ZeroDivisionError", tb)
        self.assertIn("line 2", tb)


class TestSandboxFormatEscape(BaseAssistantTest):
    def test_format_dunder_payloads_are_rejected(self):
        for code in (
            'print("{0.__globals__[frappe].conf.db_name}".format(frappe.utils.cint))',
            'print("{0.__class__.__mro__}".format(1))',
            'print("{0.__globals__}".format_map({}))',
            'print(getattr("x", "format"))',
            "import string\nstring.Formatter().vformat('{0.__globals__}', (1,), {})",
            "from string import Formatter",
            "import operator\noperator.methodcaller('format', 1)('{0.__globals__}')",
        ):
            with self.assertRaises(PermissionError, msg=code):
                sandbox._reject_private_attributes(code)

    def test_plain_code_still_allowed(self):
        sandbox._reject_private_attributes("x = 'a b'.upper()\nprint('%s-%d' % (x, 3), f'{x}')")

    def test_scrub_removes_secrets(self):
        conf = {"db_name": "d", "db_password": "p", "encryption_key": "k", "host_name": "h"}
        fake = type("F", (), {"local": type("L", (), {"conf": conf})()})()
        sandbox._scrub_conf_secrets(fake)
        self.assertEqual(set(conf), {"db_name", "host_name"})
