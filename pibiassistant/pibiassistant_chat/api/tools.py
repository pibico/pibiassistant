# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
Tool Permissions API — list tools and manage per-user approval preferences.

Bridges the AIDA settings UI to:
- PA's local tool registry (for the tool catalog shown in the UI)
- AR's AR Tool Trust DocType (for Block / Ask / Always Allow preferences)

Each AIDA session corresponds to a user on the local Frappe site, so
``frappe.session.user`` is the correct ``user_id`` to pass through to AR.
"""

import frappe
from frappe import _

from .auth import _ar_user_id

# Tools that trigger HITL approval by default when no preference is set.
# Kept in sync with DEFAULT_APPROVAL_TOOLS in AR's approval_hook.py — the UI
# surfaces this as a "requires approval by default" hint.
_DEFAULT_APPROVAL_TOOLS = frozenset(
    {
        "create_document",
        "update_document",
        "delete_document",
        "submit_document",
    }
)


_LOCAL_PREFS_KEY = "aida_tool_preferences"


def _local_tool_preferences() -> dict:
    """Per-user tool preferences stored on this site (used when PA Cloud isn't connected)."""
    raw = frappe.defaults.get_user_default(_LOCAL_PREFS_KEY, frappe.session.user)
    try:
        prefs = frappe.parse_json(raw) if raw else {}
    except Exception:
        prefs = {}
    return prefs if isinstance(prefs, dict) else {}


def _tool_to_ui_dict(tool_meta: dict, read_only: bool = False) -> dict:
    """Project a PA tool metadata dict down to the fields the UI needs.

    ``read_only`` mirrors the tool's MCP ``readOnlyHint`` (resolved from the
    same PA category source the MCP endpoint uses). The UI defaults read-only
    tools to "always allow" and write tools to "ask" — matching what AR's
    approval hook actually does at runtime, so the displayed default is truthful.
    """
    name = tool_meta.get("name", "")
    return {
        "name": name,
        "description": tool_meta.get("description", ""),
        "category": tool_meta.get("category") or "General",
        "requires_permission": tool_meta.get("requires_permission"),
        "default_requires_approval": name in _DEFAULT_APPROVAL_TOOLS,
        "read_only": read_only,
    }


def _resolve_read_only_map(tool_names: list, registry) -> dict:
    """Map each tool name to whether it is read-only (MCP readOnlyHint == true).

    Reuses the MCP endpoint's category resolver and annotation mapping so the
    settings UI and the tools/list annotation AR keys on stay in lockstep.
    Any failure degrades a tool to NOT read-only (safe default: it will "ask").
    """
    try:
        from pibiassistant.api.pa_endpoint import _resolve_tool_categories
        from pibiassistant.utils.tool_category_detector import category_to_annotations
    except ImportError:
        return {}

    try:
        categories = _resolve_tool_categories(tool_names, registry)
    except Exception:
        return {}

    return {
        name: bool(category_to_annotations(categories.get(name, "read_write")).get("readOnlyHint"))
        for name in tool_names
    }


@frappe.whitelist(methods=["GET"])
def list_available_tools():
    """
    List all tools the current user can access on this Frappe site.

    Reads directly from PA's tool registry (same-site Python call — no
    MCP round-trip) so category / description come from the source of truth.

    Returns:
            {"tools": [{name, description, category, requires_permission,
                        default_requires_approval}, ...]}
    """
    try:
        from pibiassistant.core.tool_registry import get_tool_registry
    except ImportError:
        frappe.log_error(
            title="AIDA Tool Permissions", message="pibiassistant not installed — cannot list tools"
        )
        return {"tools": []}

    registry = get_tool_registry()
    tools_meta = registry.get_available_tools(user=frappe.session.user)

    tool_names = [t.get("name", "") for t in tools_meta]
    read_only_map = _resolve_read_only_map(tool_names, registry)

    projected = [
        _tool_to_ui_dict(t, read_only=read_only_map.get(t.get("name", ""), False)) for t in tools_meta
    ]
    projected.sort(key=lambda t: (t["category"], t["name"]))
    return {"tools": projected}


@frappe.whitelist(methods=["GET"])
def list_tool_preferences():
    """
    Fetch the current user's tool approval preferences from AR.

    Returns:
            {"preferences": {tool_name: "always_allow" | "block" | "ask", ...}}
            Tools without a persistent preference are omitted (UI defaults them to "ask").
    """
    from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

    client = get_pa_cloud_client()
    if not client:
        return {"preferences": _local_tool_preferences()}

    result = client.list_tool_preferences(user_id=_ar_user_id(frappe.session.user))
    return result or {"preferences": {}}


@frappe.whitelist(methods=["POST"])
def set_tool_preference(tool_name: str | None = None, preference: str | None = None):
    """
    Set the current user's approval preference for one tool.

    Args:
            tool_name: MCP tool name (e.g. "create_document")
            preference: One of "ask", "always_allow", "block"

    Returns:
            {"success": True, "tool_name": ..., "preference": ...}
    """
    if not tool_name:
        frappe.throw(_("tool_name is required"), frappe.ValidationError)
    if preference not in ("ask", "always_allow", "block"):
        frappe.throw(
            _("preference must be one of: ask, always_allow, block"),
            frappe.ValidationError,
        )

    try:
        from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

        client = get_pa_cloud_client()
        if not client:
            prefs = _local_tool_preferences()
            if preference == "ask":
                prefs.pop(tool_name, None)
            else:
                prefs[tool_name] = preference
            frappe.defaults.set_user_default(_LOCAL_PREFS_KEY, frappe.as_json(prefs), frappe.session.user)
            return {"success": True, "tool_name": tool_name, "preference": preference}

        return client.set_tool_preference(
            user_id=_ar_user_id(frappe.session.user),
            tool_name=tool_name,
            preference=preference,
        )

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="AIDA Tool Permissions", message=f"Error setting tool preference: {e}")
        frappe.throw(_("Error saving preference: {0}").format(str(e)))


@frappe.whitelist(methods=["GET"])
def get_skipped_tools():
    """Diagnostic: list tools that failed to load (import/dependency errors),
    with the reason. Helps explain why a tool is missing from the tool list
    on a given server. System Manager only."""
    frappe.only_for("System Manager")
    from pibiassistant.utils.plugin_manager import get_plugin_manager

    pm = get_plugin_manager()
    # Ensure tools have been loaded so skipped_tools is populated.
    try:
        pm.get_all_tools()
    except Exception:
        pass
    return {"skipped_tools": getattr(pm, "skipped_tools", {})}
