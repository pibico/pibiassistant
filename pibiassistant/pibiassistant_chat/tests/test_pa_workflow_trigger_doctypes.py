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

_PAO_INSTALLED_MSG = (
    "frappe_assistant_copilot is installed on this site; "
    "it defines the same DocType names and its module sync runs last — "
    "module will read 'pibiAssistant' until AIDA is removed."
)


class TestFACWorkflowTriggerDoctypes(BaseAssistantTest):
    """The 3 PA Workflow Trigger DocTypes live in the Chat module.

    When frappe_assistant_copilot is installed alongside pibiassistant
    on the same site, PA's migrate sync runs after PA's and wins the module
    field (both apps declare the same DocType names). The module assertions are
    skipped in that case; they will pass on a PA-only site.
    """

    def _pao_installed(self) -> bool:
        return "frappe_assistant_copilot" in frappe.get_installed_apps()

    def test_pa_workflow_trigger_module_is_chat(self):
        if self._pao_installed():
            self.skipTest(_PAO_INSTALLED_MSG)
        meta = frappe.get_meta("PA Workflow Trigger")
        self.assertEqual(meta.module, "pibiAssistant Chat")
        self.assertEqual(meta.name, "PA Workflow Trigger")

    def test_pa_workflow_trigger_filter_module_is_chat(self):
        if self._pao_installed():
            self.skipTest(_PAO_INSTALLED_MSG)
        meta = frappe.get_meta("PA Workflow Trigger Filter")
        self.assertEqual(meta.module, "pibiAssistant Chat")
        self.assertEqual(meta.name, "PA Workflow Trigger Filter")

    def test_pa_workflow_trigger_filter_is_child_table(self):
        """pa_workflow_trigger_filter is a child table (istable=1).

        This assertion holds regardless of which app owns the module.
        """
        meta = frappe.get_meta("PA Workflow Trigger Filter")
        self.assertTrue(meta.istable)

    def test_pa_workflow_trigger_log_module_is_chat(self):
        if self._pao_installed():
            self.skipTest(_PAO_INSTALLED_MSG)
        meta = frappe.get_meta("PA Workflow Trigger Log")
        self.assertEqual(meta.module, "pibiAssistant Chat")
        self.assertEqual(meta.name, "PA Workflow Trigger Log")

    def test_python_controllers_importable(self):
        from pibiassistant.pibiassistant_chat.doctype.pa_workflow_trigger.pa_workflow_trigger import (
            PAWorkflowTrigger,
        )
        from pibiassistant.pibiassistant_chat.doctype.pa_workflow_trigger_filter.pa_workflow_trigger_filter import (
            PAWorkflowTriggerFilter,
        )
        from pibiassistant.pibiassistant_chat.doctype.pa_workflow_trigger_log.pa_workflow_trigger_log import (
            PAWorkflowTriggerLog,
        )

        self.assertEqual(PAWorkflowTrigger.__name__, "PAWorkflowTrigger")
        self.assertEqual(PAWorkflowTriggerFilter.__name__, "PAWorkflowTriggerFilter")
        self.assertEqual(PAWorkflowTriggerLog.__name__, "PAWorkflowTriggerLog")
