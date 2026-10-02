"""Loop 5 plugin fixes: generate_document images, run_workflow hint, DataError message,
analyze_business_data errors, dashboard sharing and chart schema, get_skill paging, file lookup, emoji."""

import re
from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.plugins.core.tools.create_document import DocumentCreate
from pibiassistant.plugins.core.tools.get_skill import GetSkill
from pibiassistant.plugins.core.tools.run_workflow import RunWorkflow
from pibiassistant.plugins.pao.tools.generate_document import GenerateDocument
from pibiassistant.tests.base_test import BaseAssistantTest

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


class TestLoop5Tools(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        frappe.local.lang = "en"

    def test_generate_document_image_without_valid_src(self):
        tool = GenerateDocument()
        html = tool._sanitize_html('<p>x</p><img alt="logo here" src="file:///etc/passwd"><img src="https://a.b/c.png" alt="ok">')
        self.assertNotIn("file:", html)
        self.assertIn("logo here", html)
        self.assertIn('src="https://a.b/c.png"', html)
        self.assertNotRegex(html, r"<img(?![^>]*src)")
        with patch.object(tool, "_generate_pdf", side_effect=KeyError("src")):
            result = tool.execute({"content": "hello", "filename": "zz-doc"})
        self.assertFalse(result["success"])
        self.assertNotEqual(result["error"], "'src'")

    def test_run_workflow_submitted_doc_suggestion(self):
        todo = frappe.get_doc({"doctype": "ToDo", "description": "ZZ wf"}).insert()
        real = frappe.get_doc("ToDo", todo.name)
        real.docstatus = 1
        with patch("frappe.get_doc", return_value=real), patch("frappe.model.workflow.get_workflow_name", return_value=None):
            result = RunWorkflow().execute({"doctype": "ToDo", "name": todo.name, "action": "Cancel"})
        self.assertFalse(result["success"])
        self.assertNotIn("update_document", result["suggestion"])
        self.assertIn("Cancel", result["suggestion"])
        real.docstatus = 0
        with patch("frappe.get_doc", return_value=real), patch("frappe.model.workflow.get_workflow_name", return_value=None):
            result = RunWorkflow().execute({"doctype": "ToDo", "name": todo.name, "action": "Submit"})
        self.assertIn("update_document", result["suggestion"])

    def test_invalid_date_values_get_specific_message(self):
        result = DocumentCreate().execute({"doctype": "ToDo", "data": {"description": "ZZ date", "date": "2026-02-30"}})
        self.assertFalse(result["success"], result)
        self.assertIn("YYYY-MM-DD", result["error"])
        self.assertNotIn("1292", result["error"])

    def test_analyze_business_data_bad_filter_is_friendly(self):
        from pibiassistant.plugins.data_science.tools.analyze_business_data import AnalyzeFrappeData

        result = AnalyzeFrappeData().execute(
            {"doctype": "Customer", "analysis_type": "profile", "filters": {"nonfield": 1}}
        )
        self.assertFalse(result["success"])
        self.assertNotIn("1054", result["error"])
        self.assertNotIn("tabCustomer", result["error"])

    def test_dashboard_sharing_reports_only_real_recipients(self):
        from pibiassistant.plugins.visualization.tools.create_dashboard import CreateDashboard
        from pibiassistant.plugins.visualization.tools.create_dashboard_chart import CreateDashboardChart

        self.assertNotIn("aggregate_function", CreateDashboardChart().inputSchema["required"])
        chart = CreateDashboardChart().execute(
            {"chart_name": "ZZ L5 Chart", "chart_type": "Bar", "doctype": "ToDo"}
        )
        self.assertTrue(chart["success"], chart)
        self.assertEqual(chart["aggregate_function"], "Count")
        result = CreateDashboard().execute(
            {"dashboard_name": "ZZ L5 Dash", "chart_names": ["ZZ L5 Chart"],
             "share_with": ["Administrator", "nobody@nowhere.com"]}
        )
        self.assertTrue(result["success"], result)
        self.assertEqual(result["permissions"], ["Administrator"])
        self.assertEqual(result["not_shared"], ["nobody@nowhere.com"])

    def test_get_skill_offset_paging(self):
        content = "".join(chr(97 + i % 26) for i in range(21000))
        skill = frappe.get_doc(
            {"doctype": "PA Skill", "skill_id": "zz-l5-long", "title": "ZZ L5 long", "status": "Published",
             "skill_type": "Workflow", "description": "zz", "content": content}
        ).insert(ignore_permissions=True)
        tool = GetSkill()
        first = tool.execute({"skill_id": skill.skill_id})["skill"]
        self.assertTrue(first["truncated"])
        self.assertEqual(first["next_offset"], 15000)
        self.assertIn("pa://skills/zz-l5-long", first["note"])
        second = tool.execute({"skill_id": skill.skill_id, "offset": first["next_offset"]})["skill"]
        self.assertFalse(second["truncated"])
        self.assertEqual(first["content"] + second["content"], content)

    def test_file_lookup_prefers_own_row(self):
        from pibiassistant.plugins.file_lookup import resolve_file_row

        other = "zz-l5-other@example.com"
        if not frappe.db.exists("User", other):
            frappe.get_doc({"doctype": "User", "email": other, "first_name": "ZZ", "send_welcome_email": 0,
                            "roles": [{"role": "Desk User"}]}).insert()
        url = "/private/files/zz-l5-dup.txt"
        names = {}
        for owner in (other, "Administrator"):
            doc = frappe.get_doc({"doctype": "File", "file_name": f"zz-l5-dup-{owner[:6]}.txt", "content": b"zz", "is_private": 1})
            doc.insert(ignore_permissions=True)
            frappe.db.set_value("File", doc.name, {"owner": owner, "file_url": url, "file_name": "zz-l5-dup.txt"})
            names[owner] = doc.name
        row = resolve_file_row(file_url=url)
        self.assertEqual(row.name, names["Administrator"])
        frappe.set_user(other)
        try:
            self.assertEqual(resolve_file_row(file_url=url).name, names[other])
        finally:
            frappe.set_user("Administrator")

    def test_run_python_code_errors_have_no_emoji(self):
        from pibiassistant.plugins.data_science.tools.run_python_code import ExecutePythonCode

        tool = ExecutePythonCode()
        blocked = tool._scan_for_dangerous_operations("eval('1')")
        self.assertFalse(blocked["success"])
        self.assertNotRegex(blocked["error"], EMOJI)
        imports = tool._check_and_handle_imports("import matplotlib.pyplot as plt\nx = 1")
        self.assertFalse(imports["success"])
        self.assertNotRegex(imports["error"], EMOJI)
        frappe.local.lang = "es"
        try:
            self.assertNotRegex(tool._scan_for_dangerous_operations("eval('1')")["error"], EMOJI)
        finally:
            frappe.local.lang = "en"

    def test_value_error_codes_map_to_format_message(self):
        from pymysql.err import DataError, OperationalError

        from pibiassistant.plugins.query_errors import client_error_message

        for exc in (DataError(1292, "Incorrect date value"), OperationalError(1264, "Out of range")):
            self.assertIn("YYYY-MM-DD", client_error_message(exc))
        self.assertNotIn("YYYY-MM-DD", client_error_message(OperationalError(1054, "Unknown column")) or "")
