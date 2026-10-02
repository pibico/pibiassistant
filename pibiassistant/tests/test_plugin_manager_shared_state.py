"""Plugin toggles must hold across workers: the database rows decide, not one worker's memory."""

import unittest

import frappe

from pibiassistant.utils.plugin_manager import PluginPersistence


class TestPluginSharedState(unittest.TestCase):
    def setUp(self):
        self.p = PluginPersistence()
        self.names = ("zz_plugin_a", "zz_plugin_b")

    def tearDown(self):
        # save_plugin_state commits, so a rollback would leave the rows behind
        for name in self.names:
            if frappe.db.exists("PA Plugin Configuration", name):
                frappe.delete_doc("PA Plugin Configuration", name, force=True, ignore_permissions=True)
        frappe.db.commit()

    def test_rows_are_read_with_the_real_doctype_name(self):
        self.assertTrue(frappe.db.table_exists("PA Plugin Configuration"))
        self.p.save_plugin_state("zz_plugin_a", True)
        self.p.save_plugin_state("zz_plugin_b", False)
        enabled = self.p._read_enabled_plugins()
        self.assertIn("zz_plugin_a", enabled)
        self.assertNotIn("zz_plugin_b", enabled)

    def test_second_toggle_does_not_undo_the_first(self):
        # worker A enables a; worker B (stale memory, never saw a) enables b
        self.p.save_plugin_state("zz_plugin_a", True)
        self.p.save_plugin_state("zz_plugin_b", True)
        self.assertTrue({"zz_plugin_a", "zz_plugin_b"} <= self.p._read_enabled_plugins())

    def test_plugin_without_row_follows_legacy_list(self):
        legacy = self.p._load_from_legacy_json()
        enabled = self.p._read_enabled_plugins()
        rows = set(frappe.get_all("PA Plugin Configuration", pluck="plugin_name"))
        self.assertTrue({n for n in legacy if n not in rows} <= enabled)
