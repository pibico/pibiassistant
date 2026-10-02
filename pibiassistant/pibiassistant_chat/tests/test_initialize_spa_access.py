# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Regression: the SPA boot path must use the single authoritative access gate.

The production lockout: ``initialize_spa`` (the SPA boot endpoint) built its
access block via ``init._build_access``, a stale COPY of ``can_use_pao`` that
still did the OLD Frappe-role check after ``can_use_pao`` had moved to
authoritative AR membership (``_is_pao_member``). A real Pending member with no
assistant Frappe role got ``can_use=False`` → lock screen, even though calling
``can_use_pao`` directly returned ``can_use=True``.

A 3rd stale copy lived in ``voice._user_can_use_pao`` (same role tuple); it is
gone and ``voice.transcribe`` now calls ``can_use_pao`` directly.

These tests pin both ``_build_access`` and ``voice.transcribe`` to the
authoritative gate so the boot path and the standalone endpoint can never
diverge again.
"""

from unittest.mock import MagicMock, patch

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

    def test_initialize_spa_queries_ar_auth_by_email_not_docname(self):
        """The SPA boot path must ask AR for auth status by the normalized AR
        identity (email), exactly like the standalone get_user_auth_status.

        Regression: initialize_spa passed the raw Frappe docname
        (frappe.session.user = "Administrator") to client.get_user_auth_status.
        AR keys AR Tenant Users by email, so the lookup found no seat →
        ready=False → the SPA rendered "Connect Your Account" on every load,
        even though the owner had an Active seat and get_user_auth_status
        (which normalizes to email) returned ready=True.
        """
        from pibiassistant.pibiassistant_chat.api import init as init_mod
        from pibiassistant.pibiassistant_chat.api.auth import _ar_user_id

        captured = {}

        def _fake_auth(user_id=None):
            captured["user_id"] = user_id
            return {
                "user_exists": True,
                "user_status": "Active",
                "has_mcp_servers": True,
                "active_server_count": 1,
                "servers_with_expired_tokens": [],
                "ready_for_streaming": True,
            }

        fake_client = MagicMock()
        fake_client.get_user_auth_status.side_effect = _fake_auth

        gate = {
            "can_use": True,
            "status": "ready",
            "show_widget": True,
            "is_admin": True,
            "user": "Administrator",
            "pa_cloud_url": "https://assistantruntime.cloud",
            "preferences": {},
        }

        # _build_user_auth returns ready=False before reading AR at all unless
        # the site itself is registered, so the state is set here rather than
        # inherited from whatever the running site happens to be.
        frappe.db.set_single_value("PA Chat Settings", "registration_status", "Registered")

        with patch(
            "pibiassistant.pibiassistant_chat.api.settings.access.can_use_pao",
            return_value=gate,
        ), patch(
            "pibiassistant.pibiassistant_chat.pa_cloud_client.get_pa_cloud_client",
            return_value=fake_client,
        ), patch("pibiassistant.pibiassistant_chat.api.init._aida_mode", return_value=False):
            result = init_mod.initialize_spa()

        expected = _ar_user_id("Administrator")
        self.assertEqual(
            captured.get("user_id"),
            expected,
            "initialize_spa must query AR auth by the email identity, not the docname",
        )
        self.assertNotEqual(
            captured.get("user_id"),
            "Administrator",
            "raw docname leaked to AR — the email-normalization sweep missed this call site",
        )
        self.assertTrue(
            result["user_auth"]["ready"],
            "a seated owner must boot ready, not to the Connect screen",
        )

    def _make_non_admin_user(self, email: str) -> str:
        """A user with NO System Manager / assistant roles, so the membership
        signal is the only thing that can grant access."""
        if not frappe.db.exists("User", email):
            u = frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": "Voice",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            )
            u.insert(ignore_permissions=True)
        u = frappe.get_doc("User", email)
        u.set("roles", [])
        u.save(ignore_permissions=True)
        return email
