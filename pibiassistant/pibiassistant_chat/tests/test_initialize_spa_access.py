# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Regression: the SPA boot path must use the single authoritative access gate.

The production lockout: ``initialize_spa`` (the SPA boot endpoint) built its
access block via ``init._build_access``, a stale COPY of ``can_use_pao`` that
still did the OLD Frappe-role check after ``can_use_pao`` had moved to
the authoritative gate. A real Pending member with no
assistant Frappe role got ``can_use=False`` → lock screen, even though calling
``can_use_pao`` directly returned ``can_use=True``.

A 3rd stale copy lived in ``voice._user_can_use_pao`` (same role tuple); it is
gone and ``voice.transcribe`` now calls ``can_use_pao`` directly.

These tests pin both ``_build_access`` and ``voice.transcribe`` to the
authoritative gate so the boot path and the standalone endpoint can never
diverge again.
"""

from unittest.mock import patch

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest


class TestInitializeSpaAccess(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def test_build_access_delegates_to_can_use_pao(self):
        """initialize_spa's access must come from the authoritative gate, not a
        stale role check. The gate's verdict is returned verbatim — the exact
        production-lockout scenario, where a member with NO assistant Frappe
        role must still get can_use=True."""
        from pibiassistant.pibiassistant_chat.api import init as init_mod

        sentinel = {
            "can_use": True,
            "status": "ready",
            "show_widget": True,
            "is_admin": False,
            "user": "paul.clinton@gmail.com",
            "pa_cloud_url": "https://assistantruntime.cloud",
            "preferences": {},
        }
        with patch(
            "pibiassistant.pibiassistant_chat.api.settings.access.can_use_pao",
            return_value=sentinel,
        ) as mock_gate:
            settings = frappe.get_single("PA Chat Settings")
            result = init_mod._build_access(settings, "paul.clinton@gmail.com", [], False)

        self.assertTrue(
            mock_gate.called,
            "_build_access must delegate to can_use_pao, not reimplement the gate",
        )
        self.assertEqual(result, sentinel, "_build_access must return can_use_pao's verdict verbatim")

    def test_voice_gate_uses_membership_not_role(self):
        """voice.transcribe must defer to the single authoritative gate
        (can_use_pao), never to its own Frappe-role check: a user the gate
        admits passes it, a user the gate denies is stopped with PermissionError
        even when they hold System Manager."""
        from types import SimpleNamespace

        from pibiassistant.pibiassistant_chat.api.voice import transcribe

        gate_path = "pibiassistant.pibiassistant_chat.api.settings.can_use_pao"

        def _gate_verdict(verdict):
            # Past the gate the next check is the missing audio part (ValidationError);
            # a denied user stops earlier with PermissionError.
            try:
                with (
                    patch(gate_path, return_value=verdict),
                    patch.object(frappe.local, "request", SimpleNamespace(files={}), create=True),
                ):
                    transcribe.__wrapped__()
            except frappe.PermissionError:
                return False
            except frappe.ValidationError:
                return True
            raise AssertionError("transcribe returned without an audio file")

        admin = self._make_non_admin_user("voice.admin@example.com")
        admin_doc = frappe.get_doc("User", admin)
        admin_doc.append("roles", {"role": "System Manager"})
        admin_doc.save(ignore_permissions=True)

        try:
            frappe.set_user(self._make_non_admin_user("voice.member@example.com"))
            self.assertTrue(_gate_verdict({"can_use": True}), "an admitted member must be allowed voice")
            self.assertFalse(_gate_verdict({"can_use": False}), "a denied user must be denied voice")

            frappe.set_user(admin)
            self.assertFalse(
                _gate_verdict({"can_use": False}),
                "a System Manager the gate denies must be denied voice",
            )
        finally:
            frappe.set_user("Administrator")

    def test_initialize_spa_is_answered_locally_in_aida_mode(self):
        """initialize_spa answers from this site: no cloud client, unlimited quota, local sessions."""
        from pibiassistant.pibiassistant_chat.api import init as init_mod

        gate = {"can_use": True, "status": "ready", "show_widget": True, "is_admin": True,
                "user": "Administrator", "preferences": {}}
        with patch("pibiassistant.pibiassistant_chat.api.settings.access.can_use_pao", return_value=gate), patch(
            "pibiassistant.pibiassistant_chat.api.init._aida_mode", return_value=True
        ), patch("pibiassistant.pibiassistant_chat.api.init._fetch_sessions", return_value=[]):
            result = init_mod.initialize_spa()

        self.assertEqual(result["access"]["mcp_endpoint_url"], "")
        self.assertTrue(result["quota"]["is_unlimited"])
        self.assertTrue(result["user_auth"]["ready"])
        self.assertEqual(result["capabilities"]["version"], "aida")
        self.assertEqual(result["sessions"], [])
        self.assertIsNone(result["outstanding"])

    def test_initialize_spa_without_access_returns_the_fail_safe_payload(self):
        from pibiassistant.pibiassistant_chat.api import init as init_mod

        gate = {"can_use": False, "status": "not_registered", "show_widget": True, "preferences": {}}
        with patch("pibiassistant.pibiassistant_chat.api.settings.access.can_use_pao", return_value=gate), patch(
            "pibiassistant.pibiassistant_chat.api.init._aida_mode", return_value=False
        ):
            result = init_mod.initialize_spa()

        self.assertFalse(result["access"]["can_use"])
        self.assertIsNone(result["user_auth"])
        self.assertEqual(result["sessions"], [])
