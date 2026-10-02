"""analyze_business_data NaN, send_email, browser_navigate_to, dashboard chart/dashboard, get_aida_status."""

import json
from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.plugins.core.tools.get_aida_status import GetAidaStatus
from pibiassistant.plugins.data_science.tools.analyze_business_data import AnalyzeFrappeData
from pibiassistant.plugins.pao.tools.browser_navigate_to import BrowserNavigateTo
from pibiassistant.plugins.pao.tools.send_email import SendEmail
from pibiassistant.plugins.visualization.tools.create_dashboard import CreateDashboard
from pibiassistant.plugins.visualization.tools.create_dashboard_chart import CreateDashboardChart
from pibiassistant.tests.base_test import BaseAssistantTest


class TestNoNaN(BaseAssistantTest):
    def _tool(self):
        tool = AnalyzeFrappeData.__new__(AnalyzeFrappeData)
        tool.logger = MagicMock()
        return tool

    def test_one_row_statistics_and_profile_are_valid_json(self):
        data = [{"amount": 5.0, "name": "a"}]
        stats = self._tool()._statistical_analysis(data, "X")
        profile = self._tool()._profile_data(data, "X")
        for out in (stats, profile):
            text = json.dumps(out, default=str)
            self.assertNotIn("NaN", text)
            json.loads(text, parse_constant=lambda c: self.fail(f"non-finite {c}"))
        self.assertIsNone(stats["statistics"]["amount"]["std"])


class TestSendEmail(BaseAssistantTest):
    def test_invalid_recipient_is_rejected(self):
        with patch("frappe.sendmail") as sendmail:
            res = SendEmail().execute({"recipients": ["notanemail"], "subject": "s", "message": "m"})
            self.assertFalse(res["success"])
            self.assertEqual(res["invalid_recipients"], ["notanemail"])
            res = SendEmail().execute(
                {"recipients": ["a@example.com"], "cc": ["bad cc"], "subject": "s", "message": "m"}
            )
            self.assertFalse(res["success"])
            sendmail.assert_not_called()

    def test_valid_queues_and_cap(self):
        with patch("frappe.sendmail") as sendmail:
            res = SendEmail().execute({"recipients": ["a@example.com"], "subject": "s", "message": "m"})
            self.assertTrue(res["success"], res)
            sendmail.assert_called_once()
            many = [f"u{i}@example.com" for i in range(60)]
            res = SendEmail().execute({"recipients": many, "subject": "s", "message": "m"})
            self.assertFalse(res["success"])


class TestNavigate(BaseAssistantTest):
    def _run(self, url):
        with patch("pibiassistant.plugins.pao.tools.browser_bridge.send_browser_tool_call"):
            return BrowserNavigateTo().execute({"url": url})

    def test_scheme_urls_rejected(self):
        for url in ("javascript:alert(1)", "data:text/html,x", "vbscript:x", "JaVaScRiPt:1", "/app/x\n<script>"):
            res = self._run(url)
            self.assertFalse(res["success"], url)

    def test_valid_routes(self):
        self.assertEqual(self._run("/app/todo")["target_url"], "/app/todo")
        self.assertEqual(self._run("Sales Invoice/SINV-0001")["target_url"], "/app/sales-invoice/sinv-0001")
        self.assertTrue(self._run(frappe.utils.get_url() + "/app/todo")["success"])


class TestDashboardTools(BaseAssistantTest):
    def test_chart_schema_and_color(self):
        schema = CreateDashboardChart().inputSchema["properties"]
        self.assertEqual(schema["aggregate_function"]["enum"], ["Count", "Sum", "Average"])
        before = frappe.db.count("Error Log")
        res = CreateDashboardChart().execute(
            {
                "chart_name": "ZZ chart color",
                "chart_type": "bar",
                "doctype": "ToDo",
                "aggregate_function": "Count",
                "based_on": "status",
                "color": "notacolor<script>",
            }
        )
        self.assertFalse(res["success"])
        self.assertIn("hex", res["error"])
        res = CreateDashboardChart().execute(
            {"chart_name": "ZZ chart group", "chart_type": "bar", "doctype": "ToDo", "aggregate_function": "Group By"}
        )
        self.assertFalse(res["success"])
        self.assertEqual(frappe.db.count("Error Log"), before)

    def test_duplicates_are_friendly(self):
        made = CreateDashboardChart().execute(
            {"chart_name": "ZZ chart dup", "chart_type": "bar", "doctype": "ToDo", "aggregate_function": "Count", "based_on": "status"}
        )
        self.assertTrue(made["success"], made)
        chart = frappe.get_doc("Dashboard Chart", made["chart_id"])
        res = CreateDashboardChart().execute(
            {"chart_name": chart.name, "chart_type": "line", "doctype": "ToDo", "aggregate_function": "Count"}
        )
        self.assertIn("already exists", res["error"])
        made = CreateDashboard().execute({"dashboard_name": "ZZ dash dup", "chart_names": [chart.name]})
        self.assertTrue(made["success"], made)
        res = CreateDashboard().execute({"dashboard_name": "ZZ dash dup", "chart_names": [chart.name]})
        self.assertIn("already exists", res["error"])


class TestAidaStatusTool(BaseAssistantTest):
    def test_admin_sees_detail_user_does_not(self):
        admin = GetAidaStatus().execute({})
        self.assertTrue(admin["success"])
        self.assertIn("admin", admin)
        with patch("frappe.get_roles", return_value=["PA User"]):
            user = GetAidaStatus().execute({})
        self.assertTrue(user["success"])
        self.assertNotIn("admin", user)
        self.assertNotIn("connections", user)

    def test_registered_in_core_plugin(self):
        from pibiassistant.plugins.core.plugin import CorePlugin

        self.assertIn("get_aida_status", CorePlugin().get_tools())
