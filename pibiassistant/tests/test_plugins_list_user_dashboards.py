"""list_user_dashboards: no cross-user listing, and shares are resolved by user/everyone."""

import frappe

from pibiassistant.plugins.visualization.tools.list_user_dashboards import ListUserDashboards
from pibiassistant.tests.base_test import BaseAssistantTest

USER = "zz-dash-viewer@example.com"


class TestListUserDashboards(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        if not frappe.db.exists("User", USER):
            frappe.get_doc(
                {"doctype": "User", "email": USER, "first_name": "ZZ", "send_welcome_email": 0}
            ).insert(ignore_permissions=True)
        self.private = self._dashboard("ZZ Private Dash")
        self.shared = self._dashboard("ZZ Shared Dash")
        self.public = self._dashboard("ZZ Public Dash")
        frappe.share.add_docshare("Dashboard", self.shared, user=USER, read=1, flags={"ignore_share_permission": True})
        frappe.share.add_docshare("Dashboard", self.public, everyone=1, read=1, flags={"ignore_share_permission": True})

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _dashboard(self, title):
        doc = frappe.get_doc({"doctype": "Dashboard", "dashboard_name": f"{title} {frappe.generate_hash(length=6)}"})
        doc.flags.ignore_mandatory = True
        return doc.insert(ignore_permissions=True).name

    def _names(self, **args):
        result = ListUserDashboards().execute(args)
        self.assertTrue(result["success"], result)
        return {d["name"]: d["access_type"] for d in result["dashboards"]}, result

    def test_low_priv_user_cannot_list_another_users_dashboards(self):
        frappe.set_user(USER)
        names, result = self._names(user="Administrator", include_shared=False)
        self.assertEqual(result["user"], USER)
        self.assertNotIn(self.private, names)

    def test_shared_and_everyone_dashboards_appear(self):
        frappe.set_user(USER)
        names, _result = self._names()
        self.assertEqual(names.get(self.shared), "shared")
        self.assertEqual(names.get(self.public), "shared")
        self.assertNotIn(self.private, names)

    def test_include_shared_false_hides_shares(self):
        frappe.set_user(USER)
        names, _result = self._names(include_shared=False)
        self.assertNotIn(self.shared, names)

    def test_system_manager_can_list_other_user(self):
        names, result = self._names(user="Administrator", include_shared=False)
        self.assertEqual(result["user"], "Administrator")
        self.assertEqual(names.get(self.private), "owner")
