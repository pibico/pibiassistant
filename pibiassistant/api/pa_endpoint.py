# pibiAssistant - AI Assistant integration for Frappe Framework
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
MCP StreamableHTTP Endpoint

Custom MCP implementation that properly handles JSON serialization
and integrates seamlessly with Frappe's existing tool infrastructure.
"""

import frappe
from frappe import _

from pibiassistant.mcp.server import MCPServer
from pibiassistant.utils.auth import check_assistant_enabled, validate_api_credentials


def _get_mcp_server_name():
    """Get MCP server name from settings or use default."""
    try:
        return frappe.db.get_single_value("PA Core Settings", "mcp_server_name") or "pibiassistant"
    except Exception:
        return "pibiassistant"


# The wrapper reads the live name per request (see MCPServer.name_resolver).
mcp = MCPServer("pibiassistant", name_resolver=_get_mcp_server_name)


def _build_tool_registry():
    """
    Build a per-request tool registry for the current user.

    Returns a fresh ``OrderedDict`` (name -> tool_dict) built on the call stack
    rather than mutating the module-level ``mcp`` instance. This keeps
    concurrent MCP requests isolated from each other: one in-flight request can
    no longer clear or overwrite the tool set another request is validating or
    executing against (issue #197). The set is also genuinely per-user, since
    ``get_available_tools`` filters by the requesting user's permissions.

    Each tool dict carries MCP annotation hints derived from its PA tool
    category, so MCP clients (e.g. Claude Desktop) can group tools into
    Read-only vs Write/delete instead of an undifferentiated "Other tools"
    bucket. The category is the same one shown/overridable on the PA admin
    page (PA Tool Configuration.tool_category) — single source of truth.

    Returns:
        OrderedDict mapping tool name to its MCP tool dict.
    """
    from collections import OrderedDict

    registry_dict = OrderedDict()
    try:
        from pibiassistant.core.tool_registry import get_tool_registry
        from pibiassistant.mcp.tool_adapter import build_tool_dict
        from pibiassistant.utils.plugin_manager import memoize_enabled_plugins
        from pibiassistant.utils.tool_category_detector import tool_annotations, tool_title

        # Every get_tool() re-syncs the enabled-plugin set from the DB; read it once.
        with memoize_enabled_plugins():
            registry = get_tool_registry()
            available_tools = sorted(
                (t for t in registry.get_available_tools(user=frappe.session.user) if t.get("name")),
                key=lambda t: t["name"],
            )

            # Resolve each tool's category once (honors admin overrides stored on
            # PA Tool Configuration; falls back to auto-detection).
            categories = _resolve_tool_categories([t["name"] for t in available_tools], registry)

            for tool_metadata in available_tools:
                tool_name = tool_metadata["name"]
                tool_instance = registry.get_tool(tool_name)
                if tool_instance:
                    tool_dict = build_tool_dict(tool_instance)
                    annotations = tool_annotations(tool_name, categories.get(tool_name, "read_write"))
                    tool_dict["title"] = tool_title(tool_name)
                    if annotations:
                        # Merge with any annotations the tool already declared.
                        tool_dict["annotations"] = {**(tool_dict.get("annotations") or {}), **annotations}
                    registry_dict[tool_name] = tool_dict

        frappe.logger().info(f"Built {len(registry_dict)} enabled tools for user {frappe.session.user}")

    except Exception as e:
        frappe.log_error(title="Tool Import Error", message=f"Error importing tools: {str(e)}")

    return registry_dict


def _resolve_tool_categories(tool_names: list, registry) -> dict:
    """
    Resolve the PA tool category for each tool name.

    Resolution order per tool:
      1. Stored ``PA Tool Configuration.tool_category`` (honors admin override).
      2. Auto-detected category via ``detect_tool_category`` (no config row yet).
      3. ``"read_write"`` fallback (maps to no annotation hints — safe default).

    Stored categories are batch-fetched in one query to avoid a DB read per tool.

    Args:
        tool_names: Tool names to resolve.
        registry: The tool registry (used to fetch instances for auto-detection).

    Returns:
        Dict mapping tool name -> category string.
    """
    from pibiassistant.utils.tool_category_detector import detect_tool_category

    categories = {}

    # 1. Batch-fetch stored categories.
    try:
        rows = frappe.get_all(
            "PA Tool Configuration",
            filters={"tool_name": ["in", tool_names]} if tool_names else {},
            fields=["tool_name", "tool_category"],
            ignore_permissions=True,
        )
        for row in rows:
            if row.get("tool_category"):
                categories[row["tool_name"]] = row["tool_category"]
    except Exception as e:
        frappe.logger().warning(f"Could not batch-fetch tool categories: {e}")

    # 2 & 3. Fill gaps via auto-detection, defaulting to read_write.
    for tool_name in tool_names:
        if tool_name in categories:
            continue
        try:
            tool_instance = registry.get_tool(tool_name)
            categories[tool_name] = detect_tool_category(tool_instance) if tool_instance else "read_write"
        except Exception:
            categories[tool_name] = "read_write"

    return categories


_AUTH_FAIL_LIMIT = 30
_AUTH_FAIL_WINDOW_SEC = 60


def _auth_fail_key():
    ip = getattr(frappe.local, "request_ip", None) or "unknown"
    return frappe.cache.make_key(f"pa_mcp_auth_fail:{ip}")


def _auth_locked_out() -> bool:
    try:
        return int(frappe.cache.get(_auth_fail_key()) or 0) >= _AUTH_FAIL_LIMIT
    except Exception:
        return False


def _record_auth_failure():
    try:
        key = _auth_fail_key()
        if frappe.cache.incrby(key, 1) == 1:
            frappe.cache.expire(key, _AUTH_FAIL_WINDOW_SEC)
    except Exception:
        frappe.logger().debug("Could not record MCP auth failure", exc_info=True)


def _unauthorized(error="unauthorized", description=None, message="Authentication required", status=401):
    """Build the 401 (or 429) response with the OAuth resource metadata hint."""
    from werkzeug.wrappers import Response

    from pibiassistant.api.oauth_discovery import get_public_base_url

    metadata_url = f"{get_public_base_url()}/.well-known/oauth-protected-resource"
    challenge = 'Bearer realm="pibiAssistant"'
    if description:
        challenge += f', error="{error}", error_description="{description}"'
    challenge += f', resource_metadata="{metadata_url}"'

    response = Response()
    response.status_code = status
    response.headers["WWW-Authenticate"] = challenge
    response.headers["Content-Type"] = "application/json"
    response.data = frappe.as_json({"error": error, "message": message})
    return response


def _authenticate_bearer(token: str):
    """Return the user for a valid, active, unexpired OAuth bearer token, else a 401 Response."""
    from frappe.utils import now_datetime

    try:
        bearer_token = frappe.get_doc("OAuth Bearer Token", {"access_token": token})
    except frappe.DoesNotExistError:
        return _unauthorized("invalid_token", "Token not found", "Token not found")
    except Exception:
        frappe.logger().error("OAuth token lookup failed", exc_info=True)
        return _unauthorized("invalid_token", "Invalid token", "Invalid token")

    if bearer_token.status != "Active":
        return _unauthorized("invalid_token", "Token is not active", "Token is not active")
    if bearer_token.expiration_time < now_datetime():
        return _unauthorized("invalid_token", "Token has expired", "Token has expired")
    if not frappe.db.get_value("User", bearer_token.user, "enabled"):
        return _unauthorized("invalid_token", "User is disabled", "User is disabled")

    # nosemgrep: frappe-setuser — user resolved from validated, non-expired OAuth bearer token
    frappe.set_user(bearer_token.user)
    return bearer_token.user


def _authenticate_mcp_request():
    """
    Authenticate MCP requests using OAuth Bearer tokens or API key/secret.

    1. OAuth 2.0 Bearer tokens: "Authorization: Bearer <token>"
    2. API Key/Secret: "Authorization: token <api_key>:<api_secret>"

    Returns the authenticated username, or a 401/429 Response. Failures are
    counted per client IP and lock the endpoint out for the rest of the window.
    """
    if _auth_locked_out():
        return _unauthorized("rate_limited", message="Too many failed attempts", status=429)

    auth_header = frappe.request.headers.get("Authorization", "")

    if auth_header.startswith("Bearer "):
        result = _authenticate_bearer(auth_header[7:])
        if isinstance(result, str):
            return result
        _record_auth_failure()
        return result

    if auth_header.startswith("token "):
        api_key, _sep, api_secret = auth_header[6:].partition(":")
        user = validate_api_credentials(api_key, api_secret)
        if user:
            # nosemgrep: frappe-setuser — user authenticated via API key:secret comparison above
            frappe.set_user(str(user))
            return str(user)
        _record_auth_failure()
        return _unauthorized("invalid_credentials", message="Invalid API credentials")

    frappe.logger().warning("No valid authentication method found in request")
    return _unauthorized()


@mcp.register(allow_guest=True, xss_safe=True, methods=["GET", "POST", "HEAD"])
def handle_mcp():
    """
    MCP StreamableHTTP endpoint.

    This is the main entry point for all MCP requests. It uses our custom
    MCP server implementation which properly handles JSON serialization.

    Endpoint: /api/method/pibiassistant.api.pa_endpoint.handle_mcp
    Protocol: MCP 2025-06-18 StreamableHTTP

    Supports two authentication methods:
    1. OAuth 2.0 Bearer tokens: "Authorization: Bearer <token>" (for web clients)
    2. API Key/Secret: "Authorization: token <api_key>:<api_secret>" (for STDIO clients)
    """
    from werkzeug.wrappers import Response

    # HEAD is the connectivity probe Claude Web sends: 401 + WWW-Authenticate advertises auth.
    if frappe.request.method == "HEAD":
        response = _unauthorized()
        response.data = b""
        return response

    # Authenticate the request (supports both OAuth and API key)
    auth_result = _authenticate_mcp_request()

    # If authentication failed, auth_result is a Response object with 401
    if isinstance(auth_result, Response):
        return auth_result

    # Authentication successful - auth_result is the username
    authenticated_user = auth_result

    # Conversation this call belongs to, when the caller is AR. Browser tools
    # read it to reach the one tab that asked; absent, they fall back to the
    # user room (every tab).
    frappe.local.ar_session_id = frappe.request.headers.get("X-AR-Session-Id") or None

    # Check if user has assistant access enabled
    if not check_assistant_enabled(authenticated_user):
        frappe.throw(
            _("PA access is disabled for user {0}").format(authenticated_user), frappe.PermissionError
        )

    # Hand the MCP server wrapper a lazy per-request registry: it is only built
    # for tools/list and tools/call, not for ping/initialize/prompts.
    return _build_tool_registry
