from unittest.mock import patch

import frappe
from pibiassistant.tests.base_test import IntegrationTestCase as UnitTestCase

from pibiassistant.pibiassistant_core.doctype.pa_audit_log.pa_audit_log import PAAuditLog


class TestAuditLogAutoname(UnitTestCase):
    def test_autoname_avoids_series_table(self):
        names = set()
        with patch("frappe.model.naming.make_autoname") as series:
            for _ in range(2):
                doc = frappe.new_doc("PA Audit Log")
                PAAuditLog.autoname(doc)
                names.add(doc.name)
        series.assert_not_called()
        self.assertEqual(len(names), 2)
        for n in names:
            self.assertRegex(n, r"^ASST-AUDIT-\d{4}-\d{2}-\d{2}-[0-9a-f]{10}$")
