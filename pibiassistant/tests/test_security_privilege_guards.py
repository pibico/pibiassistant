"""Chat/MCP write tools and the SQL tool must not reach privilege or credential data, System Manager included."""

import unittest

import frappe

from pibiassistant.core.security_config import filter_sensitive_fields, is_doctype_accessible
from pibiassistant.plugins.core.field_guard import privileged_fields_attempted
from pibiassistant.plugins.data_science.tools.run_database_query import QueryAndAnalyse


class TestPrivilegeGuards(unittest.TestCase):
    def test_privilege_doctypes_closed_for_system_manager(self):
        for dt in ("Role", "Custom DocPerm", "User Permission", "Has Role", "OAuth Client"):
            self.assertFalse(is_doctype_accessible(dt, "System Manager", "write"), dt)
            self.assertFalse(is_doctype_accessible(dt, "System Manager", "create"), dt)
            self.assertTrue(is_doctype_accessible(dt, "System Manager", "read"), dt)
        self.assertTrue(is_doctype_accessible("ToDo", "System Manager", "write"))
        self.assertTrue(is_doctype_accessible("Custom Field", "System Manager", "write"))

    def test_user_privilege_fields(self):
        self.assertEqual(sorted(privileged_fields_attempted("User", ["roles", "first_name", "enabled"])), ["enabled", "roles"])
        self.assertEqual(privileged_fields_attempted("ToDo", ["roles", "enabled"]), [])

    def test_system_manager_never_sees_secrets(self):
        doc = {"name": "x", "reset_password_key": "abc", "api_secret": "s", "client_secret": "c", "email": "a@b.c"}
        for dt in ("User", "OAuth Client"):
            out = filter_sensitive_fields(doc, dt, "System Manager")
            self.assertEqual(out["email"], "a@b.c")
            for k in ("reset_password_key", "api_secret", "client_secret"):
                self.assertEqual(out[k], "***RESTRICTED***", (dt, k))

    def test_sql_denylist(self):
        tool = QueryAndAnalyse()
        bad = [
            "SELECT * FROM __Auth", "select `password` from `__Auth`", "SELECT * FROM tabSessions",
            "SELECT reset_password_key FROM tabUser", "SELECT client_secret FROM `tabOAuth Client`",
            "SELECT LOAD_FILE('/etc/passwd')", "SELECT SLEEP(5)", "SELECT * FROM information_schema.tables",
            "SELECT * FROM mysql.user", "SELECT 1 INTO OUTFILE '/tmp/x'",
        ]
        for q in bad:
            self.assertFalse(tool._validate_query_security(q)["is_valid"], q)
        for q in ("SELECT name, status FROM tabToDo", "SELECT COUNT(*) FROM `tabSales Invoice` WHERE docstatus = 1"):
            self.assertTrue(tool._validate_query_security(q)["is_valid"], q)
