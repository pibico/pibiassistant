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

import re
from typing import Any, Dict

import frappe
from frappe import _
from frappe.model.document import Document

from pibiassistant.pibiassistant_core.server import assistantServer


MAX_PROVIDER_ROWS = 20
PROVIDER_IDS = (
    "openai", "anthropic", "deepseek", "qwen", "xai", "azure_openai", "openai_compatible",
)
AZURE_HOST_SUFFIXES = (".openai.azure.com", ".services.ai.azure.com", ".cognitiveservices.azure.com")
_SLUG_RE = re.compile(r"^[a-z0-9-]{1,40}$")


def _removed_provider_rows(rows):
    """Names of child rows stored in the DB that this save drops (their keys must go too)."""
    try:
        if not frappe.db.table_exists("PA LLM Provider"):
            return []
        stored = frappe.get_all(
            "PA LLM Provider",
            filters={"parent": "PA Core Settings", "parenttype": "PA Core Settings"},
            pluck="name",
        )
    except Exception:
        return []
    kept = {r.name for r in rows if r.name}
    return [n for n in stored if n not in kept]


def _delete_removed_provider_keys(names):
    if not names:
        return
    try:
        frappe.db.delete(
            "__Auth", {"doctype": "PA LLM Provider", "fieldname": "api_key", "name": ("in", list(names))}
        )
    except Exception as e:
        frappe.log_error(title="LLM Provider Key Cleanup Error", message=type(e).__name__)


def _normalize_url(url, allow_private):
    """Validate a base URL at save time (no DNS). Uses the providers package when present."""
    try:
        from pibiassistant.pibiassistant_chat.api.chat.providers import validate_base_url
    except ImportError:
        validate_base_url = None
    if validate_base_url:
        try:
            return validate_base_url(url, resolve=False)["url"]
        except Exception as e:
            # ProviderConfigError carries a user-safe message; anything else must not leak details.
            if type(e).__name__ == "ProviderConfigError":
                frappe.throw(str(e) or _("The base URL points to a private or reserved address"))
            raise
    return _fallback_normalize_url(url, allow_private)


def _fallback_normalize_url(url, allow_private):
    import ipaddress
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    if parts.scheme != "https" and not (allow_private and parts.scheme == "http"):
        frappe.throw(_("The base URL must start with https://"))
    if parts.username or parts.password or "@" in parts.netloc:
        frappe.throw(_("The base URL must not contain credentials"))
    if parts.query or parts.fragment:
        frappe.throw(_("The base URL must not contain a query or a fragment"))
    host = parts.hostname
    if not host:
        frappe.throw(_("The base URL must start with https://"))
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if not allow_private and (host == "localhost" or (ip is not None and not ip.is_global)):
        frappe.throw(_("The base URL points to a private or reserved address"))
    return url.rstrip("/").removesuffix("/chat/completions")


def _stored_rows():
    """{row name: (provider_id, base_url, deployment, has_key)} as saved now; {} if unavailable."""
    try:
        if not frappe.db.table_exists("PA LLM Provider"):
            return {}
        rows = frappe.get_all(
            "PA LLM Provider",
            filters={"parent": "PA Core Settings", "parenttype": "PA Core Settings"},
            fields=["name", "provider_id", "base_url", "deployment"],
        )
        keyed = {
            r[0]
            for r in frappe.db.sql(
                "select name from `__Auth` where doctype=%s and fieldname=%s", ("PA LLM Provider", "api_key")
            )
        }
    except Exception:
        return {}
    return {
        r.name: (r.provider_id, (r.base_url or "").strip(), (r.deployment or "").strip(), r.name in keyed)
        for r in rows
    }


def _new_key_entered(row):
    key = row.get("api_key") or ""
    return bool(key) and set(key) != {"*"}


def _guard_stored_key(row, stored):
    """A saved key must not be redirected: changing where it is sent needs a new key in the same save."""
    old = stored.get(row.name) if row.name else None
    if not old:
        return False
    old_pid, old_url, old_dep, has_key = old
    if row.provider_id != old_pid:
        frappe.throw(_("Row {0}: the provider cannot be changed. Remove the row and add a new one.").format(row.idx))
    moved = (row.base_url or "").strip() != old_url or (row.deployment or "").strip() != old_dep
    if moved and has_key and not _new_key_entered(row):
        frappe.throw(
            _("Row {0}: enter the API key again when you change the base URL or the deployment.").format(row.idx)
        )
    return not moved


def _check_provider_row(row, allow_private, unchanged=False):
    if row.provider_id not in PROVIDER_IDS:
        frappe.throw(_("Row {0}: choose a valid provider.").format(row.idx))
    row.label = (row.label or "").strip()[:60]
    try:
        timeout = int(row.timeout_seconds or 0)
    except (TypeError, ValueError):
        timeout = 0
    row.timeout_seconds = 120 if timeout <= 0 else max(10, min(600, timeout))
    try:
        max_tokens = int(row.max_output_tokens or 0)
    except (TypeError, ValueError):
        max_tokens = -1
    if max_tokens != 0 and not 256 <= max_tokens <= 200000:
        frappe.throw(_("Row {0}: Max output tokens must be 0 or between 256 and 200000.").format(row.idx))
    row.max_output_tokens = max_tokens

    row.default_model = (row.default_model or "").strip()
    if len(row.default_model) > 120 or " " in row.default_model:
        frappe.throw(_("Row {0}: the model name is not valid.").format(row.idx))
    models = []
    for line in (row.extra_models or "").replace(",", "\n").splitlines():
        name = line.strip()
        if not name or name in models:
            continue
        if len(name) > 120 or " " in name:
            frappe.throw(_("Row {0}: the model name is not valid.").format(row.idx))
        models.append(name)
    if len(models) > 100:
        frappe.throw(_("Row {0}: at most 100 other models are allowed.").format(row.idx))
    row.extra_models = "\n".join(models)

    try:
        _check_endpoint(row, allow_private)
    except frappe.ValidationError as e:
        if not unchanged:
            raise
        # An endpoint saved earlier (e.g. before the site flag was removed) must not make the
        # whole form unsaveable; the provider simply fails its test until fixed.
        frappe.msgprint(str(e), indicator="orange", alert=True)

    if row.enabled and row.provider_id != "openai_compatible":
        key = row.get("api_key") or ""
        if not key:
            frappe.throw(_("Enter the API key"))


def _check_endpoint(row, allow_private):
    url = (row.base_url or "").strip()
    if url:
        try:
            row.base_url = _normalize_url(url, allow_private)
        except frappe.ValidationError as e:
            frappe.throw(_("Row {0}: {1}").format(row.idx, str(e)))
    else:
        row.base_url = ""
    if row.provider_id == "openai_compatible" and not row.base_url:
        frappe.throw(_("Row {0}: enter the base URL.").format(row.idx))
    if row.provider_id == "azure_openai":
        _check_azure_row(row, allow_private)


def _check_azure_row(row, allow_private):
    from urllib.parse import urlsplit

    if not row.base_url:
        frappe.throw(_("Row {0}: enter the base URL.").format(row.idx))
    row.deployment = (row.deployment or "").strip()
    if not row.deployment:
        frappe.throw(_("Enter the deployment name"))
    row.api_version = (row.api_version or "").strip() or "2024-10-21"
    host = (urlsplit(row.base_url).hostname or "").lower()
    if not allow_private and not host.endswith(AZURE_HOST_SUFFIXES):
        frappe.throw(_("The Azure endpoint must be an address of your Azure OpenAI resource"))


def _assign_slug(row, taken):
    """Next free slug for a row without one (used in model ids d:<slug>/<model>)."""
    base = row.provider_id.replace("_", "-")
    slug, n = base, 1
    while slug in taken:
        n += 1
        slug = f"{base}-{n}"
    return slug


class PACoreSettings(Document):
    """assistant Server Settings DocType controller"""

    def onload(self):
        """Populate computed fields when document is loaded (including first time after install)"""
        self._populate_endpoint_urls()

    def before_save(self):
        """Populate computed fields before saving"""
        self._populate_endpoint_urls()

    def _populate_endpoint_urls(self):
        """Helper to populate endpoint URLs based on current site"""
        frappe_url = frappe.utils.get_url()
        self.mcp_endpoint_url = f"{frappe_url}/api/method/pibiassistant.api.pa_endpoint.handle_mcp"
        self.oauth_discovery_url = f"{frappe_url}/.well-known/openid-configuration"

    def validate(self):
        """Validate settings before saving"""
        # Plugin validation is handled by plugin manager
        self._validate_llm_providers()

    def _validate_llm_providers(self):
        """Normalise and check the direct provider rows.

        ``llm_providers`` does not exist on a site that has not migrated yet, hence the
        ``get`` access and the table_exists guard.
        """
        rows = self.get("llm_providers") or []
        self.flags.removed_llm_rows = _removed_provider_rows(rows)
        if not rows:
            return
        if len(rows) > MAX_PROVIDER_ROWS:
            frappe.throw(_("At most {0} providers can be configured.").format(MAX_PROVIDER_ROWS))

        allow_private = bool(frappe.conf.get("pa_allow_private_llm_urls"))
        taken = set()
        stored = _stored_rows()
        for row in rows:
            _check_provider_row(row, allow_private, unchanged=_guard_stored_key(row, stored))
        # Rows that already have a valid slug keep it first so a new row above cannot steal it.
        for row in rows:
            current = (row.get("slug") or "").strip()
            if current and _SLUG_RE.match(current) and current not in taken:
                row.slug = current
                taken.add(current)
            else:
                row.slug = ""
        for row in rows:
            if not row.slug:
                row.slug = _assign_slug(row, taken)
                taken.add(row.slug)

        if self.get("llm_backend_mode") in ("Direct providers", "Both") and not any(
            r.enabled for r in rows
        ):
            frappe.msgprint(
                _("No provider is enabled, so direct models will not be available."),
                indicator="orange",
                alert=True,
            )

    def enable_assistant_api(self):
        """Enable the assistant MCP API"""
        try:
            server = assistantServer()
            server.enable()

        except Exception as e:
            frappe.log_error(title=_("Failed to enable assistant MCP API"), message=str(e))
            raise

    def disable_assistant_api(self):
        """Disable the assistant MCP API"""
        try:
            server = assistantServer()
            server.disable()

        except Exception as e:
            frappe.log_error(title=_("Failed to disable assistant MCP API"), message=str(e))
            raise

    @frappe.whitelist()
    def get_mcp_server_info(self):
        """Get MCP server information (for backward compatibility with MCP Inspector)"""
        from pibiassistant import hooks

        frappe_url = frappe.utils.get_url()
        return {
            "mcp_endpoint": f"{frappe_url}/api/method/pibiassistant.api.pa_endpoint.handle_mcp",
            "mcp_transport": "StreamableHTTP",
            "mcp_protocol_version": "2025-03-26",
            "server_enabled": self.server_enabled,
            "server_info": {
                "name": hooks.app_name,
                "version": hooks.app_version,
                "description": hooks.app_description,
                "title": hooks.app_title,
                "publisher": hooks.app_publisher,
            },
        }

    # SSE Bridge methods removed - SSE transport is deprecated
    # Use StreamableHTTP (OAuth-based) transport instead

    @frappe.whitelist()
    def refresh_plugins(self):
        """Refresh the entire plugin system - discovery and tools"""
        try:
            from pibiassistant.core.tool_registry import get_tool_registry
            from pibiassistant.utils.plugin_manager import get_plugin_manager

            # Refresh plugin manager discovery
            plugin_manager = get_plugin_manager()
            plugin_manager.refresh_plugins()

            # Get statistics
            discovered_plugins = plugin_manager.get_discovered_plugins()
            enabled_plugins = plugin_manager.get_enabled_plugins()
            available_tools = plugin_manager.get_all_tools()

            # Include external tools from hooks
            tool_registry = get_tool_registry()
            external_tools = tool_registry._get_external_tools()
            available_tools.update(external_tools)

            frappe.msgprint(
                frappe._(
                    "Plugin system refreshed successfully.<br>Found {0} tools from {1} plugins.<br>Plugins: {2} enabled out of {3} discovered."
                ).format(
                    len(available_tools), len(enabled_plugins), len(enabled_plugins), len(discovered_plugins)
                )
            )

            return {
                "success": True,
                "stats": {
                    "total_tools": len(available_tools),
                    "discovered_plugins": len(discovered_plugins),
                    "enabled_plugins": len(enabled_plugins),
                },
            }

        except Exception as e:
            frappe.log_error(title=frappe._("Plugin Refresh Error"), message=str(e))
            frappe.throw(frappe._("Failed to refresh plugin system: {0}").format(str(e)))

    def on_update(self):
        """Handle settings update"""
        from pibiassistant.pibiassistant_core.server import get_server_instance

        server = get_server_instance()
        server_was_enabled = self.has_value_changed("server_enabled")

        # Handle MCP API enable/disable
        if self.server_enabled:
            if server_was_enabled or not server.running:
                # Enable API if it was just enabled or not running
                frappe.enqueue(
                    "pibiassistant.pibiassistant_core.server.enable_background_api",
                    queue="short",
                    enqueue_after_commit=True,
                )
        else:
            if server_was_enabled and server.running:
                # Disable API if it was just disabled
                self.disable_assistant_api()

        _delete_removed_provider_keys(self.flags.get("removed_llm_rows"))

        # Refresh tool registry if settings changed
        try:
            from pibiassistant.utils.tool_cache import refresh_tool_cache

            refresh_tool_cache()
        except Exception as e:
            frappe.log_error(title=frappe._("Tool Cache Refresh Error"), message=str(e))

    @frappe.whitelist()
    def get_plugin_status(self):
        """Get plugin status with a simplified view that links to PA Admin for full control"""
        try:
            from pibiassistant.core.tool_registry import get_tool_registry
            from pibiassistant.utils.plugin_manager import get_plugin_manager

            # Get plugin manager for plugin info
            plugin_manager = get_plugin_manager()
            tool_registry = get_tool_registry()
            discovered_plugins = plugin_manager.get_discovered_plugins()
            enabled_plugins = plugin_manager.get_enabled_plugins()
            available_tools = plugin_manager.get_all_tools()

            # Include external tools from hooks (registered via assistant_tools)
            external_tools = tool_registry._get_external_tools()
            available_tools.update(external_tools)

            # Count active tools
            active_tools = len(
                [
                    tool_name
                    for tool_name, tool_info in available_tools.items()
                    if tool_info.plugin_name in enabled_plugins
                ]
            )
            total_tools = len(available_tools)

            esc = frappe.utils.escape_html
            rows = []
            for plugin in discovered_plugins:
                plugin_name = plugin.get("name", "Unknown")
                is_enabled = plugin_name in enabled_plugins
                tools_count = len(plugin.get("tools", []))
                label = plugin.get("display_name", plugin_name.replace("_", " ").title())
                state = "on" if is_enabled else "off"
                rows.append(
                    f"""<li class="pa-ps__row pa-ps__row--{state}">
                        <span class="pa-ps__name">{esc(label)}</span>
                        <span class="pa-ps__meta">{esc(_("{0} tools").format(tools_count))}</span>
                        <span class="pa-ps__pill pa-ps__pill--{state}">{esc(_("Active") if is_enabled else _("Inactive"))}</span>
                    </li>"""
                )

            html = f"""
            <div class="pa-ps">
                <div class="pa-ps__summary">
                    <span class="pa-ps__title"><i class="ph ph-gear-six" aria-hidden="true"></i> {esc(_("Plugin System Status"))}</span>
                    <span class="pa-ps__stat"><span class="pa-ps__label">{esc(_("Active Tools"))}</span> <strong>{active_tools}</strong> / {total_tools}</span>
                    <span class="pa-ps__stat"><span class="pa-ps__label">{esc(_("Plugins"))}</span> <strong>{len(enabled_plugins)}</strong> / {len(discovered_plugins)}</span>
                    <span class="pa-ps__pill pa-ps__pill--on"><i class="ph ph-check-circle" aria-hidden="true"></i> {esc(_("Operational"))}</span>
                    <a class="btn btn-primary btn-xs pa-ps__open" href="/app/pa-admin"><i class="ph ph-arrow-square-out" aria-hidden="true"></i> {esc(_("Open PA Admin"))}</a>
                </div>
                <div class="pa-ps__panel">
                    <h6 class="pa-ps__heading"><i class="ph ph-puzzle-piece" aria-hidden="true"></i> {esc(_("Plugins"))}</h6>
                    <ul class="pa-ps__list">{"".join(rows)}</ul>
                    <p class="pa-ps__note"><i class="ph ph-info" aria-hidden="true"></i>
                        {esc(_("For individual tool management, role-based access control, and category filtering, use the PA Admin page."))}
                        <a href="/app/pa-admin">PA Admin</a></p>
                </div>
            </div>
            """

            return {"success": True, "html": html}

        except Exception as e:
            return {
                "success": False,
                "html": f"<div class='pa-ps__error' role='alert'>{frappe.utils.escape_html(_('Error loading plugin status'))}: {frappe.utils.escape_html(str(e))}</div>",
            }

    @frappe.whitelist()
    def toggle_plugin(self, plugin_name: str, action: str) -> Dict[str, Any]:
        """Enable or disable a plugin"""
        from pibiassistant.utils.plugin_manager import PluginError, get_plugin_manager

        if action not in ("enable", "disable"):
            frappe.throw(_("Invalid action: {0}").format(action))

        try:
            plugin_manager = get_plugin_manager()
            if action == "enable":
                result = plugin_manager.enable_plugin(plugin_name)
                message = _("Plugin '{0}' enabled successfully").format(plugin_name)
            else:
                result = plugin_manager.disable_plugin(plugin_name)
                message = _("Plugin '{0}' disabled successfully").format(plugin_name)
        except PluginError as e:
            frappe.throw(str(e))
        except Exception as e:
            frappe.log_error(title=frappe._("Plugin Toggle Error"), message=str(e))
            frappe.throw(frappe._("Failed to {0} plugin '{1}': {2}").format(action, plugin_name, str(e)))

        if not result:
            frappe.throw(_("Failed to {0} plugin '{1}'").format(action, plugin_name))
        frappe.msgprint(message)
        return {"success": True, "message": message}


# SSE Bridge API endpoints removed - SSE transport is deprecated
# Use StreamableHTTP (OAuth-based) transport instead


def get_context(context):
    context.title = _("assistant Server Settings")
    context.docs = _("Manage the settings for the assistant Server.")
    context.settings = frappe.get_doc("PA Core Settings")
