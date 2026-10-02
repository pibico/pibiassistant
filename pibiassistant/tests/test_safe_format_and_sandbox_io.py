"""Format String templates and the run_python_code sandbox must not reach files or memory."""

import json
import os
import subprocess
import sys
import unittest

from pibiassistant.utils.safe_format import safe_format


class TestSafeFormat(unittest.TestCase):
    def test_plain_fields_and_specs(self):
        self.assertEqual(safe_format("Hola {name}, {n:>4} {x:.2f} {name!r}", {"name": "Ana", "n": 7, "x": 1.234}), "Hola Ana,    7 1.23 'Ana'")

    def test_attribute_and_index_traversal_rejected(self):
        for t in ("{a.__class__}", "{a[0]}", "{a.b}"):
            with self.assertRaises(ValueError):
                safe_format(t, {"a": "x"})

    def test_nested_width_rejected(self):
        with self.assertRaises(ValueError):
            safe_format("{n:>{n}}", {"n": 10**9})
        with self.assertRaises(ValueError):
            safe_format("{n:>9999}", {"n": 1})

    def test_missing_argument_is_keyerror(self):
        with self.assertRaises(KeyError):
            safe_format("{x}", {})

    def test_output_cap(self):
        with self.assertRaises(ValueError):
            safe_format("{a}{a}", {"a": "x" * 150_000})


class TestSandboxIO(unittest.TestCase):
    def _run(self, code):
        import frappe

        bench = os.path.dirname(os.path.dirname(frappe.get_app_path("frappe")))
        sites = os.path.join(os.path.dirname(bench), "sites")
        req = {"code": code, "user": "Administrator", "site": frappe.local.site, "sites_path": sites, "limits": {"timeout_seconds": 20}}
        p = subprocess.run([sys.executable, "-m", "pibiassistant.utils.code_execution_subprocess"], input=json.dumps(req), capture_output=True, text=True, cwd=os.path.dirname(frappe.get_app_path("pibiassistant")), timeout=60)
        return json.loads(p.stdout)

    def test_io_is_blocked(self):
        for code in (
            "pd.read_json('x.json')", "pd.read_csv('x')", "np.fromfile('x')", "np.load('x')", "np.save('x', np.array([1]))",
            "pd.DataFrame({'a': [1]}).to_csv('x')", "pd.eval('1+1')", "print(np.lib)", "print(pd.io)",
        ):
            r = self._run(code)
            self.assertFalse(r["success"], code)

    def test_analysis_still_works(self):
        r = self._run("df = pd.DataFrame({'a': [1, 2, 3]})\nprint(int(df['a'].sum()), float(np.random.default_rng(1).random() < 2), float(np.linalg.norm(np.array([3.0, 4.0]))))")
        self.assertTrue(r["success"], r)
        self.assertEqual(r["output"].split()[0], "6")
        self.assertIn("5.0", r["output"])
