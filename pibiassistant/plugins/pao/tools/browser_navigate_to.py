# pibiAssistant - Browser Tools
# Copyright (C) 2025 Paul Clinton
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

"""
Browser tool to navigate to a specific URL or Frappe route.
"""

import re
import uuid
from typing import Any
from urllib.parse import urlparse

import frappe
from frappe import _

from pibiassistant.plugins.pao.tools.base_browser_tool import BaseBrowserTool


SCHEME_PREFIX = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
ILLEGAL_CHARS = re.compile(r"[\x00-\x1f\x7f<>\"`\\]")


def _is_safe_navigation_url(url: str) -> bool:
    """
    Validate a navigation target: only same-site http(s) URLs or relative
    absolute paths (not protocol-relative) are allowed.

    Mirrors the widget-side check in public/js/pao/widget_browser_tools.js
    so the server refuses attacker-supplied javascript:/data:/cross-origin
    URLs before the Socket.IO event is dispatched.
    """
    if not url:
        return False

    parsed = urlparse(url)

    # Relative path — must be absolute ("/foo") and not protocol-relative ("//foo")
    if not parsed.scheme and not parsed.netloc:
        return url.startswith("/") and not url.startswith("//")

    # Same-origin http(s)
    if parsed.scheme in ("http", "https"):
        site_origin = urlparse(frappe.utils.get_url())
        return parsed.netloc == site_origin.netloc

    return False


class BrowserNavigateTo(BaseBrowserTool):
    """
    Navigate the user's browser to a specific URL or Frappe route.

    This tool allows the assistant to:
    - Open a specific document: /app/doctype/document-name
    - Open a list view: /app/doctype
    - Open a report: /app/query-report/report-name
    - Open any Frappe route

    IMPORTANT: This tool initiates navigation and returns immediately.
    It does NOT wait for the page to load (navigation destroys the JS context).
    Use browser_get_page_context after navigation to inspect the new page.

    Note: Only navigates within the same Frappe site. External URLs are blocked.

    Navigation is fire-and-forget: the server returns success immediately and
    fires the Socket.IO event for the widget. The SPA handles navigation from
    the SSE tool_call_start event. No round-trip confirmation is needed.
    """

    def __init__(self):
        super().__init__()
        self.name = "browser_navigate_to"
        self.description = (
            "Navigate the user's browser to a specific Frappe route or URL. "
            "Use for opening documents, lists, reports, or other pages. "
            "Only same-site navigation is allowed. "
            "Returns immediately after initiating navigation."
        )

        self.inputSchema = {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "The URL or route to navigate to. Can be: "
                        "- Full path: /app/sales-invoice/SINV-00001 "
                        "- Route: app/sales-invoice/SINV-00001 "
                        "- Doctype route: Sales Invoice/SINV-00001"
                    ),
                },
            },
            "required": ["url"],
        }

        self._timeout = 15

    @property
    def tool_name(self) -> str:
        return "navigate_to"

    def get_tool_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "url": arguments.get("url"),
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Navigate is fire-and-forget: return success immediately and send the
        Socket.IO event for the widget to pick up. The SPA handles navigation
        from the SSE tool_call_start event (which includes the URL in `input`).

        No need to wait for browser confirmation — navigation destroys the
        JS context anyway, so the widget can't reliably respond.
        """
        from pibiassistant.plugins.pao.tools.browser_bridge import (
            send_browser_tool_call,
        )

        url = arguments.get("url", "")
        if not url:
            return {"success": False, "error": _("No URL provided")}

        if not isinstance(url, str) or ILLEGAL_CHARS.search(url):
            return {"success": False, "error": _("The URL contains characters that are not allowed")}

        # A scheme prefix is only acceptable on a full http(s) URL; anything else
        # ("javascript:x") would otherwise be mistaken for a doctype route below.
        if SCHEME_PREFIX.match(url) and not re.match(r"^https?://", url, re.IGNORECASE):
            return {"success": False, "error": _("Only same-site http(s) navigation allowed")}

        # Normalize the URL
        target_url = url
        if not url.startswith("/") and not url.startswith("http"):
            if url.startswith("app/") or url.startswith("Form/") or url.startswith("List/"):
                target_url = "/" + url
            else:
                # Assume Frappe doctype route like "Sales Invoice/SINV-00001"
                target_url = "/app/" + url.lower().replace(" ", "-")

        # SECURITY: Only permit same-site http(s) or absolute relative paths.
        # Blocks javascript:, data:, and cross-origin URLs before dispatch.
        if not _is_safe_navigation_url(target_url):
            return {
                "success": False,
                "error": _("Only same-site http(s) navigation allowed"),
            }

        # Fire Socket.IO event for the widget (best-effort, widget may or may not be active)
        user = frappe.session.user
        call_id = str(uuid.uuid4())
        params = self.get_tool_params(arguments)

        try:
            send_browser_tool_call(
                user=user,
                call_id=call_id,
                tool_name=self.tool_name,
                params=params,
                session_id=getattr(frappe.local, "ar_session_id", None),
            )
        except Exception:
            pass  # Widget notification is best-effort

        # Return success immediately — don't wait for browser response
        return {
            "success": True,
            "navigated": True,
            "target_url": target_url,
            "message": f"Navigation initiated to {target_url}. " "The browser will navigate shortly.",
        }
