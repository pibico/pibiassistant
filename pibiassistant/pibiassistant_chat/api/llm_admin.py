# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""Administrator endpoints behind the Direct providers table in PA Core Settings.

Nothing here returns, logs or raises key material: results carry only a status,
a host and model names.
"""

import re

import frappe
from frappe import _

from ._rate_limits import rate_limit, session_user_or_ip

_ROW_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,140}$")


def _assert_admin():
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Not permitted"), frappe.PermissionError)


def _row(row_name):
    """The saved provider row for ``row_name`` or a clear error (unsaved or not migrated)."""
    if not isinstance(row_name, str) or not _ROW_NAME_RE.match(row_name):
        frappe.throw(_("Invalid provider row."), frappe.ValidationError)
    try:
        from .llm_config import provider_by_name

        row = provider_by_name(row_name)
    except Exception:
        row = None
    if not row:
        frappe.throw(_("Save the settings first. If the table is not available yet, run migrate."))
    return row


@frappe.whitelist()
@rate_limit(session_user_or_ip, limit=10, seconds=60)
def test_provider(row_name):
    _assert_admin()
    row = _row(row_name)
    label = row.get("label") or ""
    try:
        from .chat.providers import ProviderError, get_provider

        try:
            res = get_provider(row).test()
        except ProviderError as e:
            return {"ok": False, "error": e.user_message(), "label": label}
        return {
            "ok": bool(res.get("ok")),
            "detail": res.get("detail") or "",
            "error": res.get("error") or "",
            "latency_ms": res.get("latency_ms"),
            "models": res.get("models") or [],
            "label": label,
        }
    except Exception as e:
        frappe.log_error(
            title="LLM Provider Test Error", message=f"{row.get('slug')} {type(e).__name__}"
        )
        return {"ok": False, "error": _("The connection test failed. Please try again."), "label": label}


@frappe.whitelist()
@rate_limit(session_user_or_ip, limit=10, seconds=60)
def load_provider_models(row_name):
    _assert_admin()
    row = _row(row_name)
    label = row.get("label") or ""
    try:
        from .chat.providers import ProviderError
        from .llm_config import refresh_provider_models

        try:
            models = refresh_provider_models(row_name)
        except ProviderError as e:
            return {"ok": False, "label": label, "models": [], "error": e.user_message()}
        return {"ok": True, "label": label, "models": list(models or [])[:500], "error": ""}
    except Exception as e:
        frappe.log_error(
            title="LLM Provider Models Error", message=f"{row.get('slug')} {type(e).__name__}"
        )
        return {"ok": False, "label": label, "models": [], "error": _("The model list could not be loaded.")}


@frappe.whitelist(methods=["GET"])
@rate_limit(session_user_or_ip, limit=30, seconds=60)
def get_provider_catalog():
    _assert_admin()
    try:
        from .chat.providers.registry import public_catalog

        providers = public_catalog()
    except Exception:
        providers = []
    return {
        "providers": providers,
        "allow_private": bool(frappe.conf.get("pa_allow_private_llm_urls")),
    }
