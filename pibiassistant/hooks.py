# pibiAssistant - AI Assistant for Frappe/ERPNext by pibiCo
# Copyright (C) 2025 pibiCo
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

import hashlib
import os

from . import __version__ as app_version

app_name = "pibiassistant"
app_title = "pibiAssistant"
app_publisher = "pibiCo"
app_description = "AI Assistant for Frappe/ERPNext by pibiCo"
app_logo_url = "/assets/pibiassistant/images/pibiassistant_mark.svg"
app_email = "pibico.sl@gmail.com"
app_license = "AGPL-3.0"
app_version = app_version

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/pibiassistant/css/pibiassistant.css"
# app_include_js = "/assets/pibiassistant/js/pibiassistant.js"

# include js, css files in header of web template
# web_include_css = "/assets/pibiassistant/css/pibiassistant.css"
# web_include_js = "/assets/pibiassistant/js/pibiassistant.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "pibiassistant/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
doctype_js = {"PA Skill": "public/js/pa_desk_panel.js"}
doctype_list_js = {"PA Skill": ["public/js/pa_desk_panel.js", "public/js/pa_skill_list.js"]}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# "Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install hooks can be added here if needed

after_install = [
    "pibiassistant.utils.migration_hooks.after_install",
    "pibiassistant.utils.email_invite.send_pa_admin_invite",
    "pibiassistant.utils.model_warmup.warm_paddleocr_models",
]


# Uninstallation
# ------------

# before_uninstall = "pibiassistant.uninstall.before_uninstall"
after_uninstall = "pibiassistant.utils.migration_hooks.after_uninstall"

# Fired before ANY app is uninstalled (including other apps). Used to clean up
# PA Skill rows registered by that app via its assistant_skills hook.
before_app_uninstall = "pibiassistant.utils.migration_hooks.before_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "pibiassistant.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    "PA Audit Log": "pibiassistant.utils.permissions.get_audit_permission_query_conditions",
    "Prompt Template": "pibiassistant.utils.permissions.get_prompt_permission_query_conditions",
    "PA Skill": "pibiassistant.utils.permissions.get_skill_permission_query_conditions",
}

# has_permission = {
# "Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# "ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "PA Core Settings": {
        "on_update": [
            "pibiassistant.utils.cache.invalidate_settings_cache",
            "pibiassistant.pibiassistant_chat.api.llm_config.invalidate_llm_cache",
        ]
    },
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "cron": {
        "0 0 * * *": ["pibiassistant.pibiassistant_core.server.cleanup_old_logs"],
    },
    # Hourly tasks removed - no longer needed after Assistant Connection Log removal
}

# Testing
# -------

# before_tests = "pibiassistant.install.before_tests"

# Overriding Methods
# ------------------------------
#
# Override Frappe's OAuth endpoints
# - openid_configuration: Add MCP-required fields
# - get_token: Properly handle Basic auth for client authentication
override_whitelisted_methods = {
    "frappe.integrations.oauth2.openid_configuration": "pibiassistant.api.oauth_discovery.openid_configuration",
    "frappe.integrations.oauth2.get_token": "pibiassistant.api.oauth_token.get_token",
}

# Custom Page Renderers
# ----------------------

# Handle .well-known OAuth endpoints with custom renderer
page_renderer = ["pibiassistant.api.oauth_wellknown_renderer.WellKnownRenderer"]

#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# "Task": "pibiassistant.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]


# User Data Protection
# --------------------

# user_data_fields = [
# {
# "doctype": "{doctype_1}",
# "filter_by": "{filter_by}",
# "redact_fields": ["{field_1}", "{field_2}"],
# "partial": 1,
# },
# {
# "doctype": "{doctype_2}",
# "filter_by": "{filter_by}",
# "partial": 1,
# },
# {
# "doctype": "{doctype_3}",
# "strict": False,
# },
# {
# "doctype": "{doctype_4}"
# }
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# "pibiassistant.auth.validate"
# ]

# Request Hooks
# -------------

# Handle CORS for OAuth endpoints (dynamic client registration, token endpoints, etc.)
# Sets frappe.conf.allow_cors (V15) and frappe.local.allow_cors (V16+) based on
# "Allowed Public Client Origins" setting - works immediately without restart
before_request = [
    "pibiassistant.api.oauth_cors.set_cors_for_oauth_endpoints",
    "pibiassistant.utils.warmup.prewarm_tool_registry",
]

# Automatically update python controller files with type annotations for DocTypes
# Use Developer Mode in Bench set up to auto append type annotation
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# "Logging DocType Name": 30  # days to retain logs
# }

# Standard Roles
# ---------------

standard_roles = [
    {"role": "PA User", "role_color": "#3498db"},
    {"role": "PA Admin", "role_color": "#e74c3c"},
]

# Boot
# -----

boot_session = "pibiassistant.boot.boot_session"

# Startup
# -------

before_migrate = "pibiassistant.utils.migration_hooks.before_migrate"
after_migrate = [
    "pibiassistant.startup.startup",
    "pibiassistant.utils.migration_hooks.after_migrate",
]

# Fixtures
# --------

fixtures = [
    # Both Custom Field entries must stay in ONE dict: export_fixtures writes a single
    # <doctype>.json per fixture entry, so a second "Custom Field" entry silently
    # overwrites the first and its fields never ship (that is how
    # User-assistant_enabled went missing and locked every user out of the MCP
    # endpoint, since utils/auth.check_assistant_enabled fails closed).
    {
        "doctype": "Custom Field",
        "filters": {
            "name": ["in", ["User-assistant_enabled", "File-pa_pending_chat_attachment"]]
        },
    },
    {"doctype": "Role", "filters": {"role_name": ["in", ["PA User", "PA Admin"]]}},
    # System prompt templates - these are installed via after_migrate hook
    # because they require special handling for child table data (arguments)
]

# Enhanced Plugin Architecture
# ----------------------------

# Tool discovery from external apps via hooks
assistant_tools = [
    # Core tools are discovered automatically from plugins
]

# Tool configuration overrides
assistant_tool_configs = {
    # Example tool config:
    # "document_create": {
    #     "max_batch_size": 100,
    #     "timeout": 30
    # }
}


# --- PA Chat: unconditional registration with runtime gates ---
#
# All chat hooks below are registered at every worker boot regardless of the
# `PA Core Settings.enable_pa_chat` toggle. Each consumer checks the
# gate at request time via `pibiassistant.pibiassistant_chat.gate.is_chat_enabled()`:
#
#   - Widget JS: `initAIDAWidget()` early-returns when the gate is off
#   - SPA `/aida` controller: returns 404 when off
#   - `add_to_apps_screen`: `has_permission` (can_use_pao gate) returns False
#   - `scheduler_events`: handlers early-return when off
#   - Permission hooks: cheap to keep registered; only invoked when querying
#     chat DocTypes, which doesn't happen meaningfully when chat is off
#
# This eliminates the boot-time gate entirely so toggling PA Chat from the
# admin UI takes effect immediately across all workers without `bench restart`.

# Widget assets ship unhashed and Frappe serves /assets with `max-age=43200`, so
# a browser keeps running the previous widget for up to 12h after a deploy. That
# silently splits client and server across a release — the browser-tool progress
# protocol was the first contract where an old cached widget actively broke the
# new server.
#
# The app version busts the cache across RELEASES, but semantic-release owns it
# (.releaserc rewrites __init__.py), so it never moves within one — which is
# every dev rebuild and every manual same-version deploy. A short digest of the
# widget sources covers that gap: it changes when and only when the files do,
# and unlike an mtime it agrees across workers and machines.
_WIDGET_ASSET_DIR = os.path.join(os.path.dirname(__file__), "public", "chat", "widget")


def _widget_asset_revision(directory: str = None) -> str:
    """Short digest of the widget sources, or "" when they cannot be read.

    Vendor bundles under libs/ are excluded — they are pinned and move with
    releases. A stale stamp is a caching problem; raising here is an outage,
    so every failure degrades to the release version alone.
    """
    directory = directory or _WIDGET_ASSET_DIR
    try:
        digest = hashlib.sha1()
        for name in sorted(os.listdir(directory)):
            if not name.endswith((".js", ".css")):
                continue
            # `directory` is a module-relative constant and `name` comes from
            # os.listdir of it, filtered to .js/.css — no request data here.
            path = os.path.join(directory, name)
            with open(path, "rb") as handle:  # nosemgrep: frappe-security-file-traversal
                digest.update(handle.read())
        return digest.hexdigest()[:10]
    except Exception:
        return ""


_WIDGET_ASSET_REVISION = _widget_asset_revision()
_WIDGET_ASSET_VERSION = f"{app_version}-{_WIDGET_ASSET_REVISION}" if _WIDGET_ASSET_REVISION else app_version


def _widget_asset(path: str) -> str:
    return f"{path}?v={_WIDGET_ASSET_VERSION}"


def _file_asset(url: str, relative_path: str) -> str:
    """Version a single static file by its content: nginx serves /assets with a one-year cache."""
    try:
        with open(os.path.join(os.path.dirname(__file__), relative_path), "rb") as f:
            return f"{url}?v={hashlib.sha1(f.read()).hexdigest()[:10]}"
    except OSError:
        return url


# CSS bundles for the chat widget. Loaded unconditionally; the widget JS
# decides at runtime whether to mount any UI based on the chat gate.
app_include_css = [
    _widget_asset("/assets/pibiassistant/vendor/phosphor/regular/style.css"),
    _file_asset("/assets/pibiassistant/vendor/pibico/fonts.css", "public/vendor/pibico/fonts.css"),
    _file_asset("/assets/pibiassistant/vendor/pibico/tokens.css", "public/vendor/pibico/tokens.css"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_base.css"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_robot.css"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_messages.css"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_modals.css"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_richblocks.css"),
    _file_asset("/assets/pibiassistant/css/pa_core_settings.css", "public/css/pa_core_settings.css"),
]

# JS bundles. Order matters: banner first (always meaningful), then the libs +
# core utilities + UI modules + widget entry. The widget entry calls
# `can_use_pao` (which now also reads the master `enable_pa_chat` gate)
# and bails before rendering any UI when chat is off.
app_include_js = [
    _widget_asset("/assets/pibiassistant/js/chat_banner.js"),
    # Diagnostics right after the banner: it records console and network from
    # the moment it loads, and a Desk boot error is exactly the one users
    # complain about. Depends only on the redact helper loaded immediately
    # above it, so it cannot fail to load.
    _widget_asset("/assets/pibiassistant/chat/widget/widget_diagnostics_redact.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_diagnostics_recorder.js"),
    # html2canvas-pro, not html2canvas 1.4.1. Upstream 1.4.1 (unmaintained since
    # 2022) throws "Error parsing CSS component value, unexpected EOF" on EVERY
    # Frappe Desk page: it reads an empty computed style off its own synthetic
    # <html2canvaspseudoelement> node for ::before/::after, which the Desk uses
    # everywhere. That is inside the library's own machinery, so no onclone
    # pruning can avoid it. The pro fork exposes the same `html2canvas` global
    # and API, so this is a drop-in swap.
    _widget_asset("/assets/pibiassistant/chat/widget/libs/html2canvas-pro.min.js"),
    # Vendored as-shipped except for its trailing sourceMappingURL comment, which
    # pointed at a .map we don't ship — a 404 on every Desk page with devtools open.
    _widget_asset("/assets/pibiassistant/chat/widget/libs/purify.min.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/pao_core.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/pao_logger.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_richblocks.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_ui.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_context.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_streaming.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_plan.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_templates.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_slash_menu.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_browser_tools.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_positioning.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_tooltips.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_onboarding.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_autofade.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_voice_capture.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_session.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget.js"),
]

# SPA route — always registered. `www/aida.py` returns 404 when the gate
# is off so the route exists but is inert.
website_route_rules = [
    {"from_route": "/aida/<path:app_path>", "to_route": "aida"},
]

# Apps-screen entry. `can_use_pao` enforces the chat gate at request time.
add_to_apps_screen = [
    {
        "name": "AIDA",
        "logo": "/assets/pibiassistant/images/pibiassistant_mark.svg",
        "title": "AIDA",
        "route": "/desk/pa-admin",
        "has_permission": "pibiassistant.pibiassistant_chat.api.settings.access.can_use_pao",
    }
]

# Permission filters for chat DocTypes — registered unconditionally; only
# fires when someone queries these tables, which is itself a chat-on activity.
permission_query_conditions.update(
    {
        "PA Chat Message": (
            "pibiassistant.pibiassistant_chat.utils.permissions" ".get_pao_message_permission_query_conditions"
        ),
        "PA Chat Usage Log": (
            "pibiassistant.pibiassistant_chat.utils.permissions" ".get_pao_usage_log_permission_query_conditions"
        ),
        "PA Chat User Preferences": (
            "pibiassistant.pibiassistant_chat.utils.permissions"
            ".get_pao_user_preferences_permission_query_conditions"
        ),
        # Zero-retention session blob: scoped to owner only (no System Manager
        # role exemption — only literal Administrator) to close the All-role IDOR.
        "PA Chat Session State": (
            "pibiassistant.pibiassistant_chat.doctype.pa_chat_session_state"
            ".pa_chat_session_state.get_permission_query_conditions"
        ),
    }
)

has_permission = {
    "PA Chat Message": ("pibiassistant.pibiassistant_chat.utils.permissions.has_pao_message_permission"),
    "PA Chat Usage Log": ("pibiassistant.pibiassistant_chat.utils.permissions.has_pao_usage_log_permission"),
    "PA Chat User Preferences": (
        "pibiassistant.pibiassistant_chat.utils.permissions.has_pao_user_preferences_permission"
    ),
    "PA Chat Session State": (
        "pibiassistant.pibiassistant_chat.doctype.pa_chat_session_state" ".pa_chat_session_state.has_permission"
    ),
}

# Scheduled jobs — each handler early-returns when chat is off.
scheduler_events.setdefault("daily", [])
scheduler_events["daily"].extend(
    [
        "pibiassistant.pibiassistant_chat.scheduler.retention.cleanup_old_messages",
        "pibiassistant.pibiassistant_chat.scheduler.attachment_sweep.sweep_orphan_chat_attachments",
    ]
)

default_log_clearing_doctypes = {
    "Error Log": 30,
}

user_data_fields = [
    {"doctype": "PA Chat Message", "filter_by": "user", "strict": False},
    {"doctype": "PA Chat User Preferences", "filter_by": "user", "strict": False},
    {"doctype": "PA Chat Usage Log", "filter_by": "user", "strict": False},
]

# NOTE: AIDA browser and document tools are discovered via the `plugins/pao/`
# plugin directory (see `plugins/pao/plugin.py`). They must NOT be re-listed
# in `assistant_tools` — that hook is for external apps to inject tools into
# the "custom_tools" plugin slot, and listing them here would cause the same
# tools to be registered twice with the wrong `plugin_name` (the hook copy
# overwrites the directory copy, mislabelling AIDA tools as "custom_tools").
