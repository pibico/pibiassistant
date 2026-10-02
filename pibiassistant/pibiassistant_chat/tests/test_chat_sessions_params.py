"""Pagination params are parsed and clamped; session previews come from one grouped query."""

import unittest

import frappe

from pibiassistant.pibiassistant_chat.api.chat import sessions


class TestSessionParams(unittest.TestCase):
    def test_int_param_parses_and_clamps(self):
        self.assertEqual(sessions._int_param(None, 30, 1, 100), 30)
        self.assertEqual(sessions._int_param("", 30, 1, 100), 30)
        self.assertEqual(sessions._int_param("7", 30, 1, 100), 7)
        self.assertEqual(sessions._int_param(-5, 30, 1, 100), 1)
        self.assertEqual(sessions._int_param(500, 30, 1, 100), 100)
        self.assertEqual(sessions._int_param(-3, 0, 0), 0)

    def test_non_numeric_is_a_validation_error(self):
        for bad in ("abc", "1;drop", [1]):
            with self.assertRaises(frappe.ValidationError):
                sessions._int_param(bad, 30, 1, 100)

    def test_endpoints_reject_bad_params_without_logging(self):
        user = frappe.session.user
        frappe.set_user("Administrator")
        try:
            before = frappe.db.count("Error Log")
            with self.assertRaises(frappe.ValidationError):
                sessions.get_session_history("ZZ-none", offset="abc")
            with self.assertRaises(frappe.ValidationError):
                sessions.get_user_sessions(limit="x")
            sessions.get_user_sessions(limit=-5)
            sessions.get_session_history("ZZ-none", limit=-5, offset=-1)
            self.assertEqual(frappe.db.count("Error Log"), before)
        finally:
            frappe.set_user(user)

    def test_preview_is_the_first_user_message_cut_at_100_chars(self):
        user = "Administrator"
        frappe.set_user(user)
        sid = "ZZ-preview-" + frappe.generate_hash(length=6)
        names = []
        try:
            for i, content in enumerate(["x" * 150, "second"]):
                doc = frappe.get_doc(
                    {"doctype": "PA Chat Message", "session_id": sid, "user": user, "role": "user", "content": content}
                ).insert(ignore_permissions=True)
                names.append(doc.name)
            row = next(s for s in sessions.get_user_sessions(limit=100) if s["session_id"] == sid)
            self.assertEqual(row["preview"], "x" * 100 + "...")
            self.assertEqual(row["message_count"], 2)
        finally:
            for n in names:
                frappe.delete_doc("PA Chat Message", n, force=True, ignore_permissions=True)
            frappe.db.rollback()


if __name__ == "__main__":
    unittest.main()
