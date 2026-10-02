# pibiAssistant - Retired endpoints (Tool preferences)
# AGPL-3.0 License

"""Tool preferences: RETIRED.

PA Cloud was retired and AIDA runs natively, so nothing here does anything.
The dotted paths stay whitelisted for one release so external mobile / MCP
clients get HTTP 410 with a clear message instead of a 404.
"""

import frappe

from pibiassistant.utils.retired import retired


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


@frappe.whitelist(methods=["GET"])
def list_available_tools(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def list_tool_preferences(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def set_tool_preference(*args, **kwargs):
    retired()
