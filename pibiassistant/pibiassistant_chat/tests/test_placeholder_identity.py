# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""`admin@example.com` is not an identity — it is Frappe's install fixture.

`frappe/utils/install.py` stamps `User("Administrator").email` with
`admin@example.com` on every site, and `bench new-site` has no flag to change
it. So on essentially every customer site the Administrator account carries a
placeholder address that no one can receive mail at (example.com is reserved by
RFC 2606).

`_ar_user_id` faithfully returned it, and PA then registered the tenant owner
on AR under that address: production's only tenant has
`owner_user_id = "admin@example.com"` beside a real, verified
`owner_email = "hari.madhavan@promantia.com"`.

Nothing is hardcoded here — the value is Frappe's, and the defect is that a
shared placeholder became a durable identity. The moment anyone gives
Administrator a real address, `_ar_user_id` returns something new: PA creates
a *second* AR Tenant User (a second billed seat), the placeholder seat stays
Active as an orphan, and `_is_tenant_owner` stops matching — locking the real
owner out of their own tenant.
"""

from unittest.mock import patch

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest


class TestPlaceholderEmailsAreNotIdentities(BaseAssistantTest):
    def test_frappes_install_placeholders_are_recognised(self):
        from pibiassistant.pibiassistant_chat.api.auth import _is_placeholder_email

        self.assertTrue(_is_placeholder_email("admin@example.com"))
        self.assertTrue(_is_placeholder_email("guest@example.com"))
        self.assertTrue(_is_placeholder_email("ADMIN@EXAMPLE.COM"))

    def test_a_real_address_is_not_a_placeholder(self):
        from pibiassistant.pibiassistant_chat.api.auth import _is_placeholder_email

        self.assertFalse(_is_placeholder_email("hari.madhavan@promantia.com"))
        # Only Frappe's two fixtures, not the whole reserved domain: a site
        # deliberately using example.com elsewhere is not our business.
        self.assertFalse(_is_placeholder_email("hari@example.com"))

    def test_resolution_stays_total_so_existing_tenants_keep_their_seat(self):
        """`_ar_user_id` must still return the placeholder.

        Every AR read path — membership, boot, privacy, streaming — resolves
        through here. A tenant already seated under `admin@example.com` (which
        production is) would stop matching its own seat the moment this
        returned anything else, and lose chat entirely. The placeholder is
        refused where it would become durable instead: at seat creation.
        """
        from pibiassistant.pibiassistant_chat.api.auth import _ar_user_id

        with patch("frappe.db.get_value", return_value="admin@example.com"):
            self.assertEqual(_ar_user_id("Administrator"), "admin@example.com")

    def test_a_real_administrator_email_still_resolves(self):
        """The normalization that made the owner recognizable still works."""
        from pibiassistant.pibiassistant_chat.api.auth import _ar_user_id

        with patch("frappe.db.get_value", return_value="paul@promantia.com"):
            self.assertEqual(_ar_user_id("Administrator"), "paul@promantia.com")
