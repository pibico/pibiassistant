from unittest.mock import patch

import frappe

from pibiassistant.api import assistant_api
from pibiassistant.api.admin import stats as admin_stats
from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.utils.usage_statistics import collect_usage_statistics


class TestUsageStatisticsShared(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def test_both_endpoints_return_the_same_shape(self):
        a = admin_stats.get_usage_statistics()
        with patch.object(assistant_api, "_authenticate_request", return_value="Administrator"):
            b = assistant_api.get_usage_statistics()
        self.assertTrue(a["success"] and b["success"])
        self.assertEqual(set(a["data"]), set(b["data"]))
        self.assertEqual(a["data"]["audit_logs"], b["data"]["audit_logs"])
        self.assertEqual(a["data"]["tools"], b["data"]["tools"])

    def test_collector_keys(self):
        data = collect_usage_statistics()
        self.assertEqual(set(data), {"connections", "audit_logs", "tools", "recent_activity"})
        self.assertEqual(set(data["audit_logs"]), {"total", "today", "this_week"})
