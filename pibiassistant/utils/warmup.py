# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0-or-later — see <https://www.gnu.org/licenses/>.

"""Per-worker warm-up of the tool registry (plugin discovery costs ~175 ms cold)."""

import frappe

_WARM_PREFIXES = ("/aida", "/app")
_warmed = False


def prewarm_tool_registry():
    """before_request hook: build the tool registry once per worker, on the page load that
    precedes the first chat turn, so that turn does not pay for plugin discovery."""
    global _warmed
    if _warmed or not frappe.local.request:
        return
    if not frappe.request.path.startswith(_WARM_PREFIXES):
        return
    _warmed = True
    try:
        from pibiassistant.core.tool_registry import get_tool_registry
        from pibiassistant.utils.plugin_manager import get_plugin_manager

        get_plugin_manager().get_all_tools()
        get_tool_registry()._get_external_tools()
    except Exception:
        frappe.logger("tool_registry").warning("Tool registry pre-warm failed", exc_info=True)
