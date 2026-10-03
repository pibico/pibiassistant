"""Provider error model.

Every failure of a direct LLM provider reaches the caller as a ProviderError.
Messages shown to users come only from user_message(); nothing here ever holds
key material (safe_message is scrubbed before it is stored).
"""

import re

import frappe
from frappe import _

_PATTERNS = (
    (re.compile(r"(?i)bearer\s+\S+"), "Bearer ***"),
    (re.compile(r"(?i)(https?://)[^/\s:@]+(?::[^/\s@]*)?@"), r"\1***@"),
    (re.compile(r"(?i)api[-_]?key\s*[=:]\s*\S+"), "api_key=***"),
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}"), "***"),
    (re.compile(r"[A-Za-z0-9_-]{32,}"), "***"),
)


def scrub(text, key=None):
    """Redact anything that looks like a credential from provider text."""
    text = str(text or "")
    if key and len(key) >= 4:
        text = text.replace(key, "***")
    for rx, repl in _PATTERNS:
        text = rx.sub(repl, text)
    return text


def _is_admin():
    try:
        return "System Manager" in frappe.get_roles()
    except Exception:
        return False


class ProviderError(Exception):
    def __init__(
        self, kind, safe_message="", status=None, request_id=None, retry_after=None, provider="", label=""
    ):
        super().__init__(kind)
        self.kind = kind
        self.safe_message = safe_message or ""
        self.status = status
        self.request_id = request_id
        self.retry_after = retry_after
        self.provider = provider
        self.label = label

    def __str__(self):
        return self.safe_message or self.kind

    def user_message(self):
        label = self.label or self.provider or _("The AI provider")
        detail = self.safe_message
        kind = self.kind
        if kind == "auth":
            return _("{0} rejected the API key. Ask your administrator to check the provider settings.").format(label)
        if kind == "quota":
            return _(
                "{0} reports that the account has no credit or quota left. Ask your administrator to check billing."
            ).format(label)
        if kind == "rate_limit":
            return _("{0} is receiving too many requests. Please wait a moment and try again.").format(label)
        if kind == "overloaded":
            return _("{0} is overloaded right now. Please try again in a moment.").format(label)
        if kind == "invalid_request":
            # upstream detail can name internal hosts, deployments or orgs: administrators only
            if detail and _is_admin():
                return _("{0} could not process the request: {1}").format(label, detail)
            return _("{0} could not process the request.").format(label)
        if kind == "not_found":
            return _("{0} does not know this model or deployment. Ask your administrator to check the model name.").format(
                label
            )
        if kind == "content_filter":
            return _("{0} blocked the answer with its content filter.").format(label)
        if kind == "timeout":
            return _("{0} took too long to respond. Please try again.").format(label)
        if kind == "network":
            return _("Cannot connect to {0} right now. Please try again in a moment.").format(label)
        if kind == "server":
            return _("{0} had an internal error. Please try again.").format(label)
        if kind == "unsupported":
            return _("{0} does not support this feature with the selected model: {1}").format(
                label, detail or getattr(self, "feature", "")
            )
        if kind == "config":
            return _("The provider {0} is not configured correctly: {1}").format(label, detail)
        if kind == "cancelled":
            return _("Stopped by user")
        return _("{0} had an internal error. Please try again.").format(label)


class _Kinded(ProviderError):
    KIND = "server"

    def __init__(
        self, safe_message="", status=None, request_id=None, retry_after=None, provider="", label=""
    ):
        super().__init__(self.KIND, safe_message, status, request_id, retry_after, provider, label)


def _mk(name, kind):
    return type(name, (_Kinded,), {"KIND": kind})


ProviderAuthError = _mk("ProviderAuthError", "auth")
ProviderQuotaError = _mk("ProviderQuotaError", "quota")
ProviderRateLimitError = _mk("ProviderRateLimitError", "rate_limit")
ProviderOverloadedError = _mk("ProviderOverloadedError", "overloaded")
ProviderInvalidRequestError = _mk("ProviderInvalidRequestError", "invalid_request")
ProviderNotFoundError = _mk("ProviderNotFoundError", "not_found")
ProviderContentFilterError = _mk("ProviderContentFilterError", "content_filter")
ProviderTimeoutError = _mk("ProviderTimeoutError", "timeout")
ProviderNetworkError = _mk("ProviderNetworkError", "network")
ProviderServerError = _mk("ProviderServerError", "server")
ProviderConfigError = _mk("ProviderConfigError", "config")
ProviderCancelled = _mk("ProviderCancelled", "cancelled")


class ProviderUnsupportedError(_Kinded):
    KIND = "unsupported"

    def __init__(self, safe_message="", feature="", **kw):
        super().__init__(safe_message, **kw)
        self.feature = feature


_BY_KIND = {
    c.KIND: c
    for c in (
        ProviderAuthError,
        ProviderQuotaError,
        ProviderRateLimitError,
        ProviderOverloadedError,
        ProviderInvalidRequestError,
        ProviderNotFoundError,
        ProviderContentFilterError,
        ProviderTimeoutError,
        ProviderNetworkError,
        ProviderServerError,
        ProviderUnsupportedError,
        ProviderConfigError,
        ProviderCancelled,
    )
}


def make_error(kind, safe_message="", **kw):
    return _BY_KIND.get(kind, ProviderServerError)(safe_message, **kw)


def log_provider_error(err):
    """Error Log entry with no message text from the provider."""
    try:
        frappe.log_error(
            title="LLM Provider Error",
            message=f"{getattr(err, 'provider', '')} {getattr(err, 'kind', '')} "
            f"HTTP {getattr(err, 'status', None)} request_id {getattr(err, 'request_id', None)}",
        )
    except Exception:
        pass
