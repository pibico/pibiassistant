# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest


class TestPAChatUsageLogDoctype(BaseAssistantTest):
    """The AIDA Usage Log DocType is migrated as PA Chat Usage Log."""

    def test_doctype_registered_with_renamed_name(self):
        meta = frappe.get_meta("PA Chat Usage Log")
        self.assertEqual(meta.name, "PA Chat Usage Log")

    def test_doctype_is_not_single(self):
        meta = frappe.get_meta("PA Chat Usage Log")
        self.assertFalse(meta.issingle)

    def test_doctype_module_is_chat(self):
        meta = frappe.get_meta("PA Chat Usage Log")
        self.assertEqual(meta.module, "pibiAssistant Chat")

    def test_doctype_autoname_preserved(self):
        meta = frappe.get_meta("PA Chat Usage Log")
        self.assertEqual(meta.autoname, "format:USAGE-{YYYY}-{#####}")

    def test_python_controller_class_renamed(self):
        from pibiassistant.pibiassistant_chat.doctype.pa_chat_usage_log.pa_chat_usage_log import (
            PAChatUsageLog,
        )

        # The controller class must be named PAChatUsageLog, not PAOUsageLog.
        self.assertEqual(PAChatUsageLog.__name__, "PAChatUsageLog")

    def test_old_pao_usage_log_name_not_used(self):
        """Safety check: old AIDA name must not resolve. Skips if AIDA is installed."""
        if "frappe_assistant_copilot" in frappe.get_installed_apps():
            self.skipTest(
                "frappe_assistant_copilot is installed on this site; "
                "'PAO Usage Log' resolves legitimately — skipping safety check."
            )
        with self.assertRaises(frappe.DoesNotExistError):
            frappe.get_meta("AIDA Usage Log")
