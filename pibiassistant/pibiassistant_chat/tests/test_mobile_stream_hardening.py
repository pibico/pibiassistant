"""create_web_session cookie bridge escaping and download_file_by_token serving."""

import json
import re
from unittest.mock import patch

import frappe

from pibiassistant.pibiassistant_chat.api import mobile_stream
from pibiassistant.tests.base_test import BaseAssistantTest

HOSTILE = 'x"; alert(1); //</script><script>alert(2)</script>'


class TestCookieBridge(BaseAssistantTest):
    def _lines(self, page):
        return re.findall(r"^document\.cookie = (.*);$", page, re.M)

    def test_hostile_cookie_value_round_trips_as_one_literal(self):
        page = mobile_stream._cookie_bridge_page(
            {"full_name": {"value": HOSTILE, "max_age": 60}, "sid": {"value": "abc"}}, "/app"
        )
        self.assertEqual(page.count("</script>"), 1, "only the bridge's own closing tag may remain")
        self.assertNotIn("<script>alert", page)
        lines = self._lines(page)
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0].replace("<\\/", "</"))
        self.assertTrue(first.startswith("full_name="))
        self.assertTrue(first.endswith("; path=/; SameSite=Strict; Secure; max-age=60"))
        value = first.split("=", 1)[1].split(";", 1)[0]
        self.assertNotIn('"', value)
        self.assertNotIn(" ", value)
        from urllib.parse import unquote

        self.assertEqual(unquote(value), HOSTILE)

    def test_redirect_cannot_close_the_script(self):
        page = mobile_stream._cookie_bridge_page({}, "/app/</script><script>alert(1)")
        self.assertEqual(page.count("</script>"), 1)


class TestDownloadFileByToken(BaseAssistantTest):
    def _make_non_admin_user(self, email):
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {"doctype": "User", "email": email, "first_name": "ZZ", "enabled": 1, "send_welcome_email": 0}
            ).insert(ignore_permissions=True)
        return email

    def _private_file(self, name, content):
        f = frappe.get_doc(
            {"doctype": "File", "file_name": name, "content": content, "is_private": 1}
        ).insert(ignore_permissions=True)
        self.addCleanup(lambda: frappe.delete_doc("File", f.name, force=True, ignore_permissions=True))
        return f

    def test_owner_gets_file_and_other_user_is_denied(self):
        owner = self._make_non_admin_user("zz.dl.owner@example.com")
        other = self._make_non_admin_user("zz.dl.other@example.com")
        frappe.set_user(owner)
        try:
            f = self._private_file("ZZ-dl-test.txt", b"hello" + frappe.generate_hash(length=8).encode())
            res = mobile_stream.download_file_by_token(file_url=f.file_url)
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.data.startswith(b"hello"))
            self.assertTrue(res.headers["Content-Disposition"].startswith("attachment;"))
            self.assertEqual(res.headers["X-Content-Type-Options"], "nosniff")

            frappe.set_user(other)
            with self.assertRaises(frappe.PermissionError):
                mobile_stream.download_file_by_token(file_url=f.file_url)
        finally:
            frappe.set_user("Administrator")

    def test_only_previewable_types_are_inline(self):
        for url, inline in (("/p/a.pdf", True), ("/p/a.png", True), ("/p/a.html", False), ("/p/a.svg", False)):
            res = mobile_stream._file_response(b"x", 'a"b\r\n.bin', url)
            self.assertEqual(res.headers["Content-Disposition"].startswith("inline"), inline, url)
            self.assertNotIn("\r", res.headers["Content-Disposition"])
            self.assertEqual(res.headers["Content-Disposition"].count('"'), 2)
