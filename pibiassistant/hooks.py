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

# Jinja
# ----------

# add methods and filters to jinja environment
jenv = {
    "methods": [
        "pibiassistant.utils.template_helpers.get_assistant_status",
        "pibiassistant.utils.template_helpers.get_tool_count",
    ]
}

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
    "PA Core Settings": {"on_update": "pibiassistant.utils.cache.invalidate_settings_cache"},
    "PA Audit Log": {"after_insert": "pibiassistant.utils.cache.invalidate_dashboard_cache"},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "cron": {
        "0 0 * * *": ["pibiassistant.pibiassistant_core.server.cleanup_old_logs"],
        "*/30 * * * *": ["pibiassistant.utils.cache.warm_cache"],
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
before_request = ["pibiassistant.api.oauth_cors.set_cors_for_oauth_endpoints"]

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

# boot_session = "pibiassistant.boot.boot_session"

# Startup
# -------

app_startup = "pibiassistant.startup.startup"
before_migrate = "pibiassistant.utils.migration_hooks.before_migrate"
after_migrate = [
    "pibiassistant.startup.startup",
    "pibiassistant.utils.migration_hooks.after_migrate",
]

# Fixtures
# --------

fixtures = [
    {"doctype": "Custom Field", "filters": {"dt": "User", "fieldname": ["in", ["assistant_enabled"]]}},
    {
        "doctype": "Custom Field",
        "filters": {"dt": "File", "fieldname": ["in", ["pa_pending_chat_attachment"]]},
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
#   - `doc_events` dispatcher: early-returns when off
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


# CSS bundles for the chat widget. Loaded unconditionally; the widget JS
# decides at runtime whether to mount any UI based on the chat gate.
app_include_css = [
    _widget_asset("/assets/pibiassistant/vendor/phosphor/regular/style.css"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_base.css"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_robot.css"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_messages.css"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_modals.css"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_richblocks.css"),
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
    _widget_asset("/assets/pibiassistant/chat/widget/widget_routing.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_streaming.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_plan.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_templates.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_slash_menu.js"),
    _widget_asset("/assets/pibiassistant/chat/widget/widget_quota.js"),
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

# Seed PA Chat Settings defaults on fresh install.
after_install.append("pibiassistant.pibiassistant_chat.hooks.install.after_install")

# Refresh the read-only cloud URL mirror from site_config, and log loudly
# if a registered site is being repointed (see chat/cloud_url.py).
after_migrate.append("pibiassistant.pibiassistant_chat.cloud_url.sync_cloud_url_mirror")

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

# Wildcard doc_events dispatcher.
#
# WHY A WILDCARD: PA Chat lets an admin attach a workflow to any DocType on
# their own site, including custom ones that do not exist when this file is
# read. The set of watched DocTypes is therefore only knowable at runtime, so
# there is no finite `doc_events` map that could express it. Frappe's own
# Server Script solves the same problem the same way — see
# `frappe/core/doctype/server_script/server_script_utils.py`.
#
# WHY IT IS SAFE (see chat/workflows/triggers/dispatcher.py):
#   1. Bails on in_migrate / in_install / in_patch / in_import BEFORE any DB
#      read, so schema operations are untouched and a half-migrated site can
#      never be queried through it.
#   2. Then `is_chat_enabled()` — a per-request cached flag that is 0 by
#      default. On an MCP-only site chat is off forever, so the hot path is a
#      cached boolean check and nothing else: no trigger map is loaded.
#   3. Then event allow-list, DocType blocklist, and a trigger-map lookup —
#      all in-memory, all early-returning.
#   4. `dispatch()` wraps everything in try/except and logs. A workflow-trigger
#      failure can never block or roll back a customer's document save.
#
# NOTE FOR MARKETPLACE REVIEW: the FC auditor flags any wildcard doc_events.
# This is the justification; the guards above are the mitigation.
doc_events.update(
    {
        "*": {
            "after_insert": ("pibiassistant.pibiassistant_chat.workflows.triggers.dispatcher.dispatch"),
            "on_update": ("pibiassistant.pibiassistant_chat.workflows.triggers.dispatcher.dispatch"),
            "on_submit": ("pibiassistant.pibiassistant_chat.workflows.triggers.dispatcher.dispatch"),
            "on_cancel": ("pibiassistant.pibiassistant_chat.workflows.triggers.dispatcher.dispatch"),
            "on_trash": ("pibiassistant.pibiassistant_chat.workflows.triggers.dispatcher.dispatch"),
        }
    }
)

# Scheduled jobs — each handler early-returns when chat is off.
scheduler_events["cron"].update(
    {
        "0 */6 * * *": ["pibiassistant.pibiassistant_chat.api.billing.sync.scheduled_sync_subscription"],
    }
)
scheduler_events.setdefault("daily", [])
scheduler_events["daily"].extend(
    [
        "pibiassistant.pibiassistant_chat.scheduler.retention.cleanup_old_messages",
        "pibiassistant.pibiassistant_chat.scheduler.attachment_sweep.sweep_orphan_chat_attachments",
        "pibiassistant.pibiassistant_chat.workflows.triggers.cleanup.prune_trigger_logs",
    ]
)

# frappe.enqueue has no retry policy, so a trigger fire lost to an AR outage is
# gone unless something sweeps it back up.
scheduler_events.setdefault("hourly", [])
scheduler_events["hourly"].append(
    "pibiassistant.pibiassistant_chat.workflows.triggers.sweeper.sweep_failed_trigger_fires"
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
