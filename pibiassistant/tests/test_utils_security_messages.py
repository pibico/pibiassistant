import re
import unittest
from unittest.mock import MagicMock, patch

import frappe

from pibiassistant.utils.read_only_db import ReadOnlyDatabase
from pibiassistant.utils.user_context import secure_user_context

EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿]")


class TestSecurityMessages(unittest.TestCase):
    def setUp(self):
        self.db = ReadOnlyDatabase(MagicMock())

    def _msg(self, fn):
        with self.assertRaises((frappe.ValidationError, AttributeError)) as ctx:
            fn()
        return str(ctx.exception)

    def test_read_only_db_errors_have_no_emoji_and_keep_types(self):
        messages = [
            self._msg(lambda: self.db.sql("")),
            self._msg(lambda: self.db.sql("DELETE FROM tabUser")),
            self._msg(lambda: self.db.sql("TRUNCATE tabUser")),
            self._msg(lambda: self.db.sql("GRANT ALL ON x")),
            self._msg(lambda: self.db.sql("SELECT 1 UNION ALL DELETE FROM tabUser")),
            self._msg(lambda: self.db.set_value),
            self._msg(lambda: self.db.something_unknown),
        ]
        for message in messages:
            self.assertFalse(EMOJI.search(message), message)
            self.assertIn("Security", message)

    def test_messages_go_through_translation(self):
        with patch("pibiassistant.utils.read_only_db._", side_effect=lambda s: "ES:" + s):
            self.assertTrue(self._msg(lambda: self.db.sql("")).startswith("ES:"))

    def test_user_context_errors_have_no_emoji(self):
        with patch.object(frappe, "get_roles", return_value=["Desk User"]):
            with self.assertRaises(frappe.PermissionError) as ctx:
                with secure_user_context():
                    pass
        self.assertFalse(EMOJI.search(str(ctx.exception)))
        self.assertIn("System Manager", str(ctx.exception))
