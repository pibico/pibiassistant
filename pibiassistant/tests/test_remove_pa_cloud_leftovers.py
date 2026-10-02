# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""patches.v3_1.remove_pa_cloud_leftovers: safe on fresh sites, idempotent, never silent about data."""

from unittest.mock import patch

import frappe

from pibiassistant.patches.v3_1 import remove_pa_cloud_leftovers as patch_module
from pibiassistant.tests.base_test import BaseAssistantTest


class TestRemovePaCloudLeftovers(BaseAssistantTest):
    def test_removed_doctypes_are_gone_from_the_app(self):
        for doctype, _cloud_only in patch_module.REMOVED_DOCTYPES:
            self.assertFalse(frappe.db.exists("DocType", doctype), doctype)

    def test_runs_twice_without_error_when_there_is_nothing_to_remove(self):
        with (
            patch.object(patch_module.frappe.db, "exists", return_value=False),
            patch.object(patch_module.frappe.db, "table_exists", return_value=False),
            patch.object(patch_module, "_log") as log,
        ):
            patch_module.execute()
            patch_module.execute()
        log.assert_not_called()

    def test_a_missing_doctype_and_table_is_skipped_quietly(self):
        with patch.object(patch_module, "_log") as log:
            patch_module._remove_doctype("PA Not A Real Doctype", True)
        log.assert_not_called()

    def test_a_doctype_that_is_not_cloud_only_is_never_dropped_while_it_holds_rows(self):
        with (
            patch.object(patch_module.frappe.db, "exists", return_value=True),
            patch.object(patch_module.frappe.db, "table_exists", return_value=True),
            patch.object(patch_module.frappe.db, "sql", return_value=[[3]]),
            patch.object(patch_module.frappe, "delete_doc") as delete_doc,
            patch.object(patch_module.frappe.db, "sql_ddl") as ddl,
            patch.object(patch_module, "_log") as log,
        ):
            patch_module._remove_doctype("PA Some Doctype", False)
        delete_doc.assert_not_called()
        ddl.assert_not_called()
        logged = " ".join(str(c.args[0]) for c in log.call_args_list)
        self.assertIn("3 row(s)", logged)
        self.assertIn("left in place", logged)

    def test_a_cloud_only_table_with_rows_is_saved_before_it_is_dropped(self):
        with (
            patch.object(patch_module.frappe.db, "exists", return_value=True),
            patch.object(patch_module.frappe.db, "table_exists", return_value=True),
            patch.object(patch_module.frappe.db, "sql", return_value=[[2]]),
            patch.object(patch_module, "_dump_rows", return_value="/tmp/dump.json") as dump,
            patch.object(patch_module.frappe, "delete_doc") as delete_doc,
            patch.object(patch_module.frappe.db, "sql_ddl") as ddl,
            patch.object(patch_module, "_log"),
        ):
            patch_module._remove_doctype("PA Some Doctype", True)
        dump.assert_called_once_with("PA Some Doctype")
        delete_doc.assert_called_once()
        ddl.assert_called_once()

    def test_a_failed_dump_leaves_the_table_in_place(self):
        with (
            patch.object(patch_module.frappe.db, "exists", return_value=True),
            patch.object(patch_module.frappe.db, "table_exists", return_value=True),
            patch.object(patch_module.frappe.db, "sql", return_value=[[2]]),
            patch.object(patch_module, "_dump_rows", side_effect=OSError("disk full")),
            patch.object(patch_module.frappe, "delete_doc") as delete_doc,
            patch.object(patch_module.frappe.db, "sql_ddl") as ddl,
            patch.object(patch_module, "_log"),
        ):
            patch_module._remove_doctype("PA Some Doctype", True)
        delete_doc.assert_not_called()
        ddl.assert_not_called()
