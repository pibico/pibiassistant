# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Shared utilities used across AIDA API modules."""

import re

import frappe
from frappe import _

from pibiassistant.pibiassistant_chat.aida_mode import is_aida_mode  # noqa: F401
from pibiassistant.pibiassistant_chat.api.llm_config import llm_ready


_SESSION_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,100}")


def _validate_session_id(session_id) -> None:
    """Reject non-string / malformed session ids before they reach an ORM filter."""
    if not isinstance(session_id, str) or not _SESSION_ID_RE.fullmatch(session_id):
        frappe.throw(_("Invalid session"), frappe.ValidationError)


def _require_system_manager():
    """Check if current user is System Manager. Throws if not."""
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(_("Only System Managers can access billing features"), frappe.PermissionError)


# The chat gate: AIDA key set or a usable direct provider (see llm_config.llm_ready).
_aida_mode = llm_ready


def _not_registered_error() -> str:
    """Message for chat actions attempted while no AIDA API key is configured."""
    return _("AIDA is not configured on this site.")


# The Error Log `title` column is capped at 140 chars by Frappe. Keep a safe
# margin so our titles never trip CharacterLengthExceededError.
_ERROR_LOG_TITLE_MAX = 120

# Stripped from SDK error messages before we show them to users. Frappe wraps
# dynamic values in <strong> tags for its own UI — that's noise in a toast.
_STRONG_TAG_RE = re.compile(r"</?strong>", re.IGNORECASE)

# Cloud-service internals that must never land in a tenant Error Log.
_UPSTREAM_TABLE_RE = re.compile(r"`tabAR [^`]+`")
_UPSTREAM_TABLE_BARE_RE = re.compile(r"\btabAR [A-Za-z0-9 ]+")
_UPSTREAM_MODULE_RE = re.compile(r"assistant_runtime(?:_[a-z]+)?(?:\.[A-Za-z0-9_.]+)?")
_RECORD_CHANGED_RE = re.compile(
    r"Record has changed since last read in table '[^']+'",
    re.IGNORECASE,
)


def _strip_noise(text: str) -> str:
    """Remove Frappe-internal HTML markup that leaks through server_messages."""
    if not text:
        return ""
    return _STRONG_TAG_RE.sub("", text).strip()


def _redact_upstream_internals(text: str) -> str:
    """Strip cloud-service table names, modules, and SQL from log text.

    Tenant Error Log is visible to the site's System Managers. Raw exceptions
    from the assistant service (``tabAR …``, MariaDB 1020, module paths) must
    not appear there.
    """
    if not text:
        return ""
    out = _UPSTREAM_TABLE_RE.sub("[internal table]", text)
    out = _UPSTREAM_TABLE_BARE_RE.sub("[internal table]", out)
    out = _UPSTREAM_MODULE_RE.sub("[service]", out)
    out = _RECORD_CHANGED_RE.sub("Record has changed since last read", out)
    out = out.replace("AR stream_error", "PA Chat stream error")
    return out


def _log(title: str, detail: str | None = None, *, message: str | None = None) -> None:
    """Write a server-side Error Log entry with correct title/message order.

    Frappe's signature is `log_error(title, message, ...)` — passing a long
    dynamic f-string as the first positional trips the 140-char Title cap and
    raises `CharacterLengthExceededError`. Always pass the short identifier
    as title and the variable detail as message.

    `message=` is accepted as an alias for `detail=` to match the kwarg name
    older callers used; either works. When both are passed, `detail` wins.

    When called from inside an `except` block, the active exception's
    traceback is appended automatically so callers don't have to remember
    to include it. This makes shallow legacy callers traceback-rich without
    a 50-site rewrite.
    """
    import sys

    try:
        safe_title = _redact_upstream_internals(title or "PA Chat Error")[:_ERROR_LOG_TITLE_MAX]
        message = (detail if detail is not None else message) or ""
        # If we're inside an `except` block, sys.exc_info() returns the
        # active triple. Append the traceback unless the caller already
        # included one (avoid duplicates from `_handle_ar_error`).
        exc_type, exc_val, _tb = sys.exc_info()
        if exc_val is not None and "Traceback" not in message:
            message = f"{message}\n\n{frappe.get_traceback(with_context=False)}"
        message = _redact_upstream_internals(message)
        frappe.log_error(title=safe_title, message=message)
    except Exception:
        # log_error itself can fail (read-only replica, DB gone, nested
        # transaction). Don't mask the original error — but emit a
        # stderr-level breadcrumb so we know the log persistence failed.
        try:
            frappe.logger("aida").exception(f"AIDA _log: failed to persist Error Log (title={title!r})")
        except Exception:
            pass


def _handle_generic_error(context: str, e: Exception, *, user_message: str | None = None) -> str:
    """Log + translate for exceptions that aren't from the SDK.

    Like `_handle_ar_error` but without AR-specific message mapping. Use for
    local Frappe errors (DB, validation, etc.). Framework-level ValidationError
    and PermissionError messages are already user-written, so we pass those
    through verbatim.
    """
    detail = f"context: {context}\ntype: {type(e).__name__}\nerror: {e}\n{frappe.get_traceback()}"
    _log(title=f"AIDA: {context}", detail=detail)

    # Framework errors are safe to surface as-is — Frappe authors write them
    # for end users (e.g. "Mandatory fields required: Billing Email").
    if isinstance(e, frappe.ValidationError | frappe.PermissionError):
        return _strip_noise(str(e))
    return user_message or _("Something went wrong. Please try again or contact support.")


def _safe_error(e: Exception, log_title: str, *, default: str | None = None) -> str:
    """Log the error server-side and return a message that is safe to show the user."""
    return _handle_generic_error(log_title, e, user_message=default)
