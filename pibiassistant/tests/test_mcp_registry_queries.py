import os
import subprocess
import sys

import frappe

from pibiassistant.api.pa_endpoint import _build_tool_registry
from pibiassistant.tests.base_test import BaseAssistantTest


class TestRegistryBuild(BaseAssistantTest):
    def _count_queries(self, fn):
        counter = {"n": 0}
        original = frappe.db.sql

        def spy(*args, **kwargs):
            counter["n"] += 1
            return original(*args, **kwargs)

        frappe.db.sql = spy
        try:
            return fn(), counter["n"]
        finally:
            del frappe.db.sql

    def test_build_is_cheap_and_sorted(self):
        _build_tool_registry()  # warm imports and caches
        registry, queries = self._count_queries(_build_tool_registry)
        self.assertTrue(registry)
        self.assertLessEqual(queries, 8, f"registry build issued {queries} queries")
        names = list(registry)
        self.assertEqual(names, sorted(names))

    def test_order_is_stable_across_hash_seeds(self):
        code = (
            "from pibiassistant.api.pa_endpoint import _build_tool_registry;"
            "frappe.set_user('Administrator');"
            "print('ORDER', ','.join(_build_tool_registry()))"
        )
        bench = os.path.abspath(os.path.join(frappe.get_app_path("pibiassistant"), "..", "..", ".."))
        outputs = set()
        for seed in ("1", "2", "3"):
            proc = subprocess.run(
                ["bench", "--site", frappe.local.site, "console"],
                input=code + "\n",
                capture_output=True,
                text=True,
                cwd=bench,
                env={**os.environ, "PYTHONHASHSEED": seed},
                timeout=180,
            )
            lines = [line for line in proc.stdout.splitlines() if "ORDER" in line]
            self.assertTrue(lines, proc.stdout[-500:] + proc.stderr[-500:])
            outputs.add(lines[-1].split("ORDER", 1)[1])
        self.assertEqual(len(outputs), 1)
