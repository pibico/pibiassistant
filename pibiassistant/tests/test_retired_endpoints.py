# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""PA Cloud endpoints were retired: the dotted paths stay whitelisted for one release and answer HTTP 410.

Also pins the endpoints that are still live (called by the AIDA SPA, the widget, Desk forms
and PA Admin) so a future clean-up cannot turn a real function into a stub by accident.
"""

import importlib
import inspect

import frappe

from pibiassistant.tests.base_test import BaseAssistantTest
from pibiassistant.utils.retired import RetiredEndpointError, retired

API = "pibiassistant.pibiassistant_chat.api."

RETIRED = {
    "analytics": [
        "get_analytics_data",
        "get_conversation_analytics",
        "get_message_credits",
    ],
    "auth": [
        "connect_aida_mcp_server",
        "get_user_mcp_servers",
        "reconnect_mcp_server",
        "disconnect_mcp_server",
    ],
    "billing.checkout": [
        "initiate_plan_upgrade",
        "reauthorize_mandate",
        "verify_payment",
        "verify_razorpay_payment",
        "verify_razorpay_credit_payment",
    ],
    "billing.combined": [
        "get_billing_page_data",
        "get_billing_details",
        "save_billing_details",
    ],
    "billing.credits": [
        "get_credit_balance",
        "purchase_credits",
        "get_expiring_credits",
        "get_consumption_breakdown",
    ],
    "billing.dashboard": [
        "get_billing_dashboard",
        "get_plan_options",
        "get_available_gateways",
    ],
    "billing.hosted": [
        "create_hosted_checkout",
    ],
    "billing.invoices": [
        "download_invoice_pdf",
    ],
    "billing.pricing": [
        "preview_plan_pricing",
        "validate_promo_code",
    ],
    "billing.quota": [
        "get_quota_status",
    ],
    "billing.seats": [
        "add_user_seat",
        "verify_seat_payment",
        "remove_user_seat",
        "preview_seat_charge",
    ],
    "billing.subscription": [
        "get_usage_history",
        "get_invoices",
        "get_subscription_status",
        "get_billing_history",
        "downgrade_to_free",
        "cancel_scheduled_change",
        "cancel_subscription",
        "reactivate_subscription",
        "get_payment_methods",
        "get_payment_instrument",
        "update_payment_method",
    ],
    "billing.sync": [
        "sync_subscription_status",
    ],
    "connections": [
        "list_connections",
        "remove_connection",
        "set_connection_enabled",
        "test_connection",
        "set_tool_visibility",
        "add_connection",
        "begin_connect",
        "get_connect_session",
        "commit_connect",
        "abandon_connect",
        "begin_reauth",
    ],
    "documents": [
        "list_documents",
        "get_document",
        "list_chunks",
        "upload_document",
        "delete_document",
        "update_document_access",
        "get_document_content",
        "get_storage_info",
    ],
    "events": [
        "get_message_events",
        "get_tool_stats",
    ],
    "marketplace": [
        "list_listings",
        "get_listing",
        "import_listing",
        "update_listing",
        "delete_listing",
        "rate_listing",
        "report_listing",
        "list_pending_reviews",
        "approve_listing",
        "reject_listing",
        "get_creator_stats",
        "list_my_listings",
        "publish_workflow",
        "download_listing_as_json",
        "check_workflow_update",
        "check_all_workflow_updates",
    ],
    "memories": [
        "list_memories",
        "delete_memory",
        "update_memory",
        "delete_all_memories",
        "get_memory_stats",
        "get_memory_summary",
    ],
    "mobile_stream": [
        "stream_chat",
        "get_available_models",
    ],
    "models": [
        "set_preferred_model",
    ],
    "notifications": [
        "get_notifications",
        "dismiss_notification",
    ],
    "packs": [
        "list_packs",
        "get_pack_contents",
        "set_industry",
        "set_pack_enabled",
        "get_recommended_pack",
        "dismiss_pack_recommendation",
        "activate_free_pack",
        "toggle_purchased_pack",
        "initiate_pack_checkout",
        "verify_pack_payment",
        "list_pack_purchases",
    ],
    "privacy": [
        "update_my_data",
        "update_my_consent",
        "get_privacy_config",
        "update_privacy_config",
        "save_initial_consent",
    ],
    "profile": [
        "get_profile",
        "update_profile",
    ],
    "prompts": [
        "get_suggested_prompts",
        "update_pinned_templates",
    ],
    "routing_preferences": [
        "list_routing_preferences",
        "create_routing_preference",
        "set_routing_preference_status",
        "set_routing_preference_mode",
        "delete_routing_preference",
        "forecast_routing_preference",
    ],
    "settings.capabilities": [
        "get_capabilities",
        "get_ar_terms",
    ],
    "settings.mobile_usage": [
        "get_usage_stats",
        "get_usage_history",
        "get_subscription_info",
        "get_model_usage",
    ],
    "settings.registration": [
        "validate_partner_code",
        "register_with_ar",
        "get_registration_state",
        "get_plan_comparison",
        "complete_email_verification",
        "accept_updated_terms",
        "request_site_rebind",
        "poll_for_rotated_secret",
        "run_diagnostics",
    ],
    "support": [
        "get_environment",
        "create_ticket",
        "download_ticket_attachment",
        "upload_ticket_attachment",
        "submit_feedback",
        "list_my_tickets",
        "list_my_feedback",
        "get_ticket_thread",
        "reply_to_ticket",
    ],
    "team_instructions": [
        "get_shared_knowledge",
        "update_shared_knowledge",
        "share_memory_to_knowledge",
    ],
    "tools": [
        "list_available_tools",
        "list_tool_preferences",
        "set_tool_preference",
    ],
    "users": [
        "list_users",
        "get_user_limit_status",
        "suspend_user",
        "deregister_user",
        "add_user",
        "get_available_users",
        "set_user_credit_limit",
        "get_my_credit_status",
        "invite_user",
        "revoke_invite",
        "resend_invite",
        "list_invites",
        "get_member_audit_log",
    ],
    "workflow_triggers": [
        "list_triggers",
        "create_trigger",
        "update_trigger",
        "delete_trigger",
        "toggle_trigger",
        "get_doctype_fields",
        "list_filterable_doctypes",
        "get_trigger_log",
        "test_trigger",
    ],
    "workflows": [
        "list_workflows",
        "create_workflow",
        "get_workflow",
        "update_workflow",
        "delete_workflow",
        "execute_workflow",
        "cancel_workflow_run",
        "get_workflow_run",
        "list_workflow_runs",
        "get_workflow_audit_summary",
        "set_workflow_schedule",
        "validate_workflow_graph",
        "test_workflow_node",
        "run_workflow_node",
        "list_user_tools",
        "resolve_workflow_tools",
    ],
}

# Retired endpoints that were open to guests keep that flag (the 410 must reach external clients).
RETIRED_GUEST = {("settings.registration", "validate_partner_code")}

# Endpoints something live still calls: AIDA SPA (public/aida/js), chat widget, Desk form JS,
# PA Admin sidebar, hooks.py, patches. They must stay real functions.
LIVE = {
    "aida": ["get_overview", "get_models", "test_connections"],
    "auth": ["get_user_auth_status", "get_user_info", "register_mobile_client"],
    "chat.cancel": ["cancel_stream"],
    "chat.hitl": ["get_pending_interrupt"],
    "chat.messages": ["send_message", "resume_interrupt"],
    "chat.sessions": ["get_session_history", "get_user_sessions", "archive_session"],
    "discovery": ["should_show_banner", "dismiss_banner", "get_chat_status", "toggle_chat", "get_chat_analytics"],
    "mobile_stream": ["create_web_session", "download_file_by_token"],
    "models": ["get_available_models"],
    "privacy": ["export_my_data", "erase_my_data", "restrict_my_processing"],
    "prompts": ["get_prompt_templates", "get_rendered_prompt"],
    "settings.access": ["can_use_pao"],
    "settings.registration": ["reset_registration"],
    "settings.uploads": ["upload_message_file"],
    "settings.widget": ["get_widget_settings"],
    "tools": ["get_skipped_tools"],
    "voice": ["transcribe"],
}


def _resolve(module, name):
    return getattr(importlib.import_module(API + module), name)


def _unwrapped(fn):
    return inspect.unwrap(fn)


class TestRetiredEndpoints(BaseAssistantTest):
    def test_every_retired_path_exists_is_whitelisted_and_has_the_stub_signature(self):
        count = 0
        for module, names in RETIRED.items():
            for name in names:
                fn = _resolve(module, name)
                with self.subTest(path=f"{module}.{name}"):
                    self.assertIn(fn, frappe.whitelisted, f"{module}.{name} lost its whitelist")
                    params = inspect.signature(fn).parameters
                    self.assertEqual(list(params), ["args", "kwargs"])
                    count += 1
        self.assertGreaterEqual(count, 15)

    def test_every_retired_path_answers_http_410_with_the_retirement_message(self):
        for module, names in RETIRED.items():
            for name in names:
                fn = _resolve(module, name)
                with self.subTest(path=f"{module}.{name}"):
                    with self.assertRaises(RetiredEndpointError) as ctx:
                        frappe.call(fn, foo="bar")
                    self.assertEqual(ctx.exception.http_status_code, 410)
                self.assertIn("PA Cloud was retired", str(ctx.exception))

    def test_helper_raises_a_validation_error_subclass_with_status_410(self):
        self.assertTrue(issubclass(RetiredEndpointError, frappe.ValidationError))
        with self.assertRaises(RetiredEndpointError):
            retired()
        self.assertEqual(RetiredEndpointError.http_status_code, 410)

    def test_guest_flag_is_kept_where_the_original_allowed_guests(self):
        for module, name in RETIRED_GUEST:
            self.assertIn(_resolve(module, name), frappe.guest_methods)

    def test_package_level_paths_still_resolve(self):
        pkg = importlib.import_module(API.rstrip("."))
        for name in ("get_credit_balance", "list_workflows", "list_users", "get_profile", "list_documents"):
            self.assertTrue(callable(getattr(pkg, name)), name)

    def test_live_endpoints_are_real_functions(self):
        for module, names in LIVE.items():
            for name in names:
                fn = _resolve(module, name)
                with self.subTest(path=f"{module}.{name}"):
                    self.assertTrue(callable(fn))
                    inner = _unwrapped(fn)
                    self.assertNotIn("retired", inner.__code__.co_names)
                    self.assertIn(fn, frappe.whitelisted)
