"""Tests must never touch the persistent QA login: the e2e suite depends on its roles."""

import os
import unittest

QA_EMAIL = "aida-qa@pibico.es"
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestQaUserGuard(unittest.TestCase):
    def test_no_test_references_the_qa_user(self):
        offenders = []
        for root, _dirs, files in os.walk(APP_DIR):
            if "/node_modules" in root or "/public" in root:
                continue
            for name in files:
                if not (name.startswith("test_") and name.endswith(".py")):
                    continue
                path = os.path.join(root, name)
                if path == os.path.abspath(__file__):
                    continue
                with open(path, encoding="utf-8") as fh:
                    if QA_EMAIL in fh.read():
                        offenders.append(os.path.relpath(path, APP_DIR))
        self.assertEqual(offenders, [], "use a ZZ user and restore state in tearDown")
