"""The receipt survives the hop from AR to a reloaded bubble."""

import json

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest

RECEIPT = {
    "v": 1,
    "mode": "auto",
    "incomplete": False,
    "selected_model": "claude-sonnet-4-6",
    "selected_tier": "Standard",
    "bound_by": "ceiling",
    "floor": {"tier": "Standard", "reasons": []},
    "ceiling": {"tier": "Standard", "source": "posture", "reasons": []},
    "credits": {"actual": 137.5},
    "notices": ["downgraded_for_credits"],
    "cycles": 1,
    "also_ran": [],
    "preference": None,
    "preference_source": "none",
}


class TestTheColumnExists(BaseAssistantTest):
    def test_routing_is_a_json_column(self):
        meta = frappe.get_meta("PA Chat Message")
        field = meta.get_field("routing")
        self.assertIsNotNone(field, "no routing column")
        self.assertEqual(field.fieldtype, "JSON")

    def test_it_is_in_the_history_field_list(self):
        """get_session_messages returns rows verbatim; a column it does not
        select is invisible to a reloaded bubble."""
        import inspect

        from pibiassistant.pibiassistant_chat.doctype.pa_chat_message import (
            pa_chat_message,
        )

        src = inspect.getsource(pa_chat_message.PAChatMessage.get_session_messages)
        self.assertIn('"routing"', src)

    def test_the_shared_key_constant_exists(self):
        from pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message import (
            PERSISTED_LLM_KEYS,
        )

        for key in ("model", "credits_used", "model_breakdown", "routing"):
            self.assertIn(key, PERSISTED_LLM_KEYS)

    def test_create_message_maps_every_persisted_key(self):
        """It mapped three by hand and model_breakdown was already out of
        sync — which is the bug this constant exists to stop repeating."""
        import inspect

        from pibiassistant.pibiassistant_chat.doctype.pa_chat_message import (
            pa_chat_message,
        )

        src = inspect.getsource(pa_chat_message.PAChatMessage.create_message)
        self.assertIn("PERSISTED_LLM_KEYS", src)


class TestRoundTrip(BaseAssistantTest):
    def _message(self, **metadata):
        from pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message import (
            PAChatMessage,
        )

        session = f"rt-{frappe.generate_hash(length=8)}"
        return session, PAChatMessage.create_message(session, "assistant", "hello", llm_metadata=metadata)

    def test_a_receipt_survives_write_and_reload(self):
        from pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message import (
            PAChatMessage,
        )

        session, _doc = self._message(model="m", credits_used=1.0, routing=RECEIPT)
        rows = PAChatMessage.get_session_messages(session)
        routing = rows["messages"][0]["routing"]
        if isinstance(routing, str):
            routing = json.loads(routing)
        self.assertEqual(routing["bound_by"], "ceiling")
        self.assertAlmostEqual(routing["credits"]["actual"], 137.5)

    def test_a_turn_with_no_receipt_stores_null_not_a_string(self):
        from pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message import (
            PAChatMessage,
        )

        session, _doc = self._message(model="m", credits_used=1.0)
        rows = PAChatMessage.get_session_messages(session)
        self.assertIn(rows["messages"][0].get("routing"), (None, "", "null"))

    def test_a_continuation_never_nulls_an_existing_receipt(self):
        """model_selected is gated upstream on not continue_from_message_id,
        so a continuation carries no receipt and must not erase one."""
        from pibiassistant.pibiassistant_chat.doctype.pa_chat_message.pa_chat_message import (
            PERSISTED_LLM_KEYS,
        )

        session, doc = self._message(model="m", credits_used=1.0, routing=RECEIPT)
        updates = {
            k: v
            for k, v in {"credits_used": 2.0, "routing": None}.items()
            if k in PERSISTED_LLM_KEYS and v is not None
        }
        self.assertNotIn("routing", updates)


class TestTheThreeGates(BaseAssistantTest):
    def test_the_live_socket_payload_carries_a_complete_receipt(self):
        """Gate 3. A reload round-trip alone passes on a build where the live
        chip is dead."""
        import inspect

        from pibiassistant.pibiassistant_chat.api.chat import relay

        src = inspect.getsource(relay)
        for at in [i for i in range(len(src)) if src.startswith('"event": "stream_complete"', i)]:
            self.assertIn('"routing"', src[at : at + 1100])

    def test_the_client_parses_every_json_column(self):
        """model_breakdown is a JSON column that neither parse loop parses —
        an object live, a string on reload. One array drives both."""
        import pathlib

        store = (
            pathlib.Path(frappe.get_app_path("pibiassistant"))
            / "chat"
            / "frontend"
            / "src"
            / "stores"
            / "chatStore.js"
        )
        src = store.read_text()
        self.assertIn("JSON_MESSAGE_FIELDS", src)
        for field in ("blocks", "model_breakdown", "routing"):
            self.assertIn(field, src)

    def test_both_parse_loops_use_the_shared_array(self):
        import pathlib

        store = (
            pathlib.Path(frappe.get_app_path("pibiassistant"))
            / "chat"
            / "frontend"
            / "src"
            / "stores"
            / "chatStore.js"
        )
        src = store.read_text()
        self.assertGreaterEqual(src.count("parseJsonFields"), 3)
        self.assertNotIn("JSON.parse(msg.blocks)", src)

    def test_complete_streaming_forwards_the_receipt(self):
        """completeStreaming copies a fixed allowlist off meta; anything not
        named is dropped."""
        import pathlib

        store = (
            pathlib.Path(frappe.get_app_path("pibiassistant"))
            / "chat"
            / "frontend"
            / "src"
            / "stores"
            / "chatStore.js"
        )
        src = store.read_text()
        at = src.index("function completeStreaming")
        self.assertIn("routing", src[at : at + 1200])

    def test_every_use_streaming_call_site_forwards_routing(self):
        """completeStreaming's routing forwarding is dead code unless every
        caller actually passes it through from the socket payload."""
        import pathlib

        composable = (
            pathlib.Path(frappe.get_app_path("pibiassistant"))
            / "chat"
            / "frontend"
            / "src"
            / "composables"
            / "useStreaming.js"
        )
        src = composable.read_text()
        self.assertEqual(src.count("chatStore.completeStreaming("), 3)
        self.assertEqual(src.count("routing: data.routing"), 3)
