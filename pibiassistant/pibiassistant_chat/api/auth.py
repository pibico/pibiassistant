# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Identity helpers, mobile OAuth client registration and the widget auth-status check.

The PA Cloud account/MCP-server endpoints (connect/reconnect/disconnect and the user
MCP server list) were retired and answer HTTP 410.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from pibiassistant.pibiassistant_chat.api._helpers import _aida_mode
from pibiassistant.pibiassistant_chat.gate import is_chat_enabled
from pibiassistant.utils.retired import retired

from ._helpers import _safe_error

_FRAPPE_PLACEHOLDER_EMAILS = frozenset({"admin@example.com", "guest@example.com"})


def _is_placeholder_email(email) -> bool:
    """True for the addresses Frappe stamps on every site at install.

    `frappe/utils/install.py` gives User "Administrator" the email
    `admin@example.com` and "Guest" `guest@example.com`, and `bench new-site`
    has no option to set a real one. They are shared by every Frappe install
    in existence and, being under an RFC 2606 reserved domain, can never
    receive mail — so they identify nobody. Frappe treats the same pair as
    non-addresses in `core/doctype/role/role.py`.
    """
    return str(email or "").strip().lower() in _FRAPPE_PLACEHOLDER_EMAILS


def _ar_user_id(user=None):
    """Resolve a Frappe user to the email AR keys its AR Tenant User by.

    AR identifies tenant users by email. For ordinary staff the Frappe username
    already IS their email, so this is a pass-through. The account that differs
    is Administrator (username "Administrator"), which must resolve to its
    User.email so the site owner is recognized as the tenant owner on AR rather
    than orphaned under a non-email username. Falls back to the raw username
    only if the User carries no email (should not happen for a real login).

    This deliberately still returns Frappe's `admin@example.com` placeholder
    when that is what the User carries. Resolution has to stay total: every AR
    read path goes through here (membership, boot, privacy, streaming), and
    tenants already registered under the placeholder would lose their seat
    match — and their chat — the moment it resolved to anything else. The
    placeholder is rejected where it would become *durable*, at seat creation
    in `_register_user_with_ar`, not here.

    Note this is the AR-facing identity ONLY. Local OAuth Bearer Tokens still
    key on the Frappe username (the User docname) — see _register_user_with_ar.
    """
    user = user or frappe.session.user
    if "@" in str(user):
        return user
    email = frappe.db.get_value("User", user, "email")
    return email or user






# ============================================================================
# Auto-Recovery Helpers
# ============================================================================
# These functions transparently re-register users and refresh tokens when AR
# doesn't recognize a previously working user (e.g., after data cleanup).








# OAuth callback must accept guest requests by definition; returns a static
# 200 with no state side effects, so it cannot leak anything.
@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep: guest-whitelisted-method
def oauth_callback() -> dict:
    """
    Placeholder OAuth callback endpoint.
    Not actually used for client_credentials flow, but required by OAuth Client doctype.
    """
    return {"status": "ok"}














# ============================================================================
# Mobile App OAuth Support - Dynamic Client Registration (RFC 7591)
# ============================================================================

# Allowed non-http redirect URI schemes for mobile app deep-linking.
# Any scheme not listed here falls back to same-origin https validation.
ALLOWED_REDIRECT_SCHEMES = {"paomobile"}


def _validate_redirect_uri(redirect_uri: str) -> str:
    """
    Validate the redirect_uri supplied by an unauthenticated caller.

    Accepts either a custom-scheme URI from the mobile app allowlist
    (e.g. paomobile://...) or an https URL on the same origin as this
    Frappe site. Anything else is rejected to prevent attacker-controlled
    redirect targets being persisted on an OAuth Client.

    Args:
            redirect_uri: The candidate redirect URI string.

    Returns:
            The validated redirect_uri (unchanged) on success.

    Raises:
            frappe.ValidationError: If the URI fails validation.
    """
    from urllib.parse import urlparse

    parsed = urlparse(redirect_uri or "")
    site_origin = urlparse(frappe.utils.get_url())

    if parsed.scheme in ALLOWED_REDIRECT_SCHEMES:
        return redirect_uri
    if parsed.scheme == "https" and parsed.netloc == site_origin.netloc:
        return redirect_uri

    frappe.throw(
        _("redirect_uri must use paomobile:// or match the site origin"),
        frappe.ValidationError,
    )


def _register_mobile_oauth_client(redirect_uri: str, device_id: str | None = None):
    """
    Dynamically register an OAuth Client for a AIDA mobile app instance.

    Follows OAuth 2.0 Dynamic Client Registration (RFC 7591) pattern.
    Each mobile device gets its own client registration for better security.

    Args:
            redirect_uri: The app's OAuth callback URI (e.g., paomobile://oauth/callback)
            device_id: Optional device identifier for unique client per device

    Returns:
            OAuth Client document
    """
    # Generate unique client_id if device_id provided, otherwise use standard
    if device_id:
        client_id = f"pao-mobile-{device_id[:16]}"
    else:
        client_id = "pao-mobile"

    # Check if client already exists
    existing = frappe.db.get_value("OAuth Client", {"client_id": client_id}, "name")
    if existing:
        client = frappe.get_doc("OAuth Client", existing)
        # SECURITY: Never let an unauthenticated caller mutate the stored
        # redirect_uris. Registration is idempotent — if the caller's
        # redirect_uri does not match what we already have on file, refuse.
        existing_uris = (client.redirect_uris or "").split()
        if redirect_uri and redirect_uri not in existing_uris:
            frappe.throw(
                _(
                    "OAuth client already registered for this device with a "
                    "different redirect_uri. Contact an administrator to reset."
                ),
                frappe.ValidationError,
            )
        return client

    # Create new OAuth Client for mobile app
    # Uses Authorization Code flow with PKCE (public client - no secret required)
    client = frappe.get_doc(
        {
            "doctype": "OAuth Client",
            "app_name": "AIDA Mobile",
            "scopes": "all openid",
            "redirect_uris": redirect_uri,
            "default_redirect_uri": redirect_uri,
            "grant_type": "Authorization Code",
            "response_type": "Code",
            "skip_authorization": 0,  # User must approve on first login
            "token_endpoint_auth_method": "None",  # PKCE public client - no secret
            "allowed_roles": [{"role": "All"}],
        }
    )

    # OAuth Client names by random hash and forces client_id = name (read-only
    # in validate()), so a plain insert would discard our client_id. Pin the
    # docname via set_name so client_id == name == the stable per-device id,
    # making the dedup above idempotent (one client per device, not one per call).
    try:
        client.insert(set_name=client_id, ignore_permissions=True)
    except frappe.DuplicateEntryError:
        # Lost a cold-start race or the row already exists — converge on it.
        pass
    return frappe.get_doc("OAuth Client", client_id)


@frappe.whitelist(methods=["GET"])
def get_user_info() -> dict:
    """
    Get current user's info for the mobile app.

    Returns user profile data after successful OAuth authentication.

    Returns:
            dict: {
                    "name": str (user id/email),
                    "email": str,
                    "full_name": str,
                    "user_image": str (URL),
                    "roles": list
            }
    """
    user = frappe.session.user

    if user == "Guest":
        frappe.throw(_("Not authenticated"), frappe.AuthenticationError)

    user_doc = frappe.get_doc("User", user)
    roles = frappe.get_roles(user)

    return {
        "name": user,
        "email": user_doc.email or user,
        "full_name": user_doc.full_name or user,
        "user_image": user_doc.user_image,
        "roles": roles,
    }


# RFC 7591 Dynamic Client Registration must be reachable pre-auth (mobile
# first run). Protected by 10/hour per-IP rate limit below.
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(key="ip", limit=10, seconds=3600)
def register_mobile_client(redirect_uri: str | None = None, device_id: str | None = None) -> dict:
    """
    Dynamic Client Registration for AIDA mobile app.

    Implements OAuth 2.0 Dynamic Client Registration (RFC 7591).
    Called by mobile app to register itself before OAuth flow.

    Rate-limited to 10 registrations per hour per source IP to prevent
    abuse by unauthenticated callers.

    Args:
            redirect_uri: The app's OAuth callback URI (default: paomobile://oauth/callback)
            device_id: Optional unique device identifier

    Returns:
            dict: {
                    "success": bool,
                    "client_id": str,
                    "authorization_endpoint": str,
                    "token_endpoint": str,
                    "revocation_endpoint": str
            }
    """
    try:
        # Check if PA Chat is enabled first (master gate)
        if not is_chat_enabled():
            return {"success": False, "pao_enabled": False, "error": _("AIDA is not enabled on this site")}

        # Default redirect URI for AIDA mobile app
        if not redirect_uri:
            redirect_uri = "paomobile://oauth/callback"

        # Validate redirect_uri scheme/origin before touching OAuth Client
        redirect_uri = _validate_redirect_uri(redirect_uri)

        # Dynamically register OAuth client
        client = _register_mobile_oauth_client(redirect_uri, device_id)

        site_url = frappe.utils.get_url()

        return {
            "success": True,
            "pao_enabled": True,
            "client_id": client.client_id,
            "authorization_endpoint": f"{site_url}/api/method/frappe.integrations.oauth2.authorize",
            "token_endpoint": f"{site_url}/api/method/frappe.integrations.oauth2.get_token",
            "revocation_endpoint": f"{site_url}/api/method/frappe.integrations.oauth2.revoke_token",
            "scopes": "all openid",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",  # PKCE public client
        }

    except Exception as e:
        frappe.log_error(
            title="AIDA Mobile OAuth Error", message=f"Error registering mobile OAuth client: {e!s}"
        )
        return {"success": False, "error": _safe_error(e, "AIDA Mobile OAuth Error")}


# Legacy alias for backwards compatibility — inherits the guest-auth and
# rate-limit rationale from register_mobile_client.
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
def ensure_mobile_oauth_client() -> dict:
    """Legacy alias - use register_mobile_client instead."""
    return register_mobile_client()


def _is_tenant_owner(ar_user_id) -> bool:
    """Always False: tenant ownership lived in PA Cloud, which no longer exists."""
    return False


@frappe.whitelist(methods=["GET"])
def get_user_auth_status() -> dict:
    """Check if the current user is ready to use AIDA (widget onboarding calls this).

    AIDA runs natively, so a configured site is always ready and an unconfigured one
    has nothing to connect to.
    """
    if _aida_mode():
        return {
            "success": True,
            "ready": True,
            "site_registered": True,
            "user_registered": True,
            "has_mcp_servers": False,
            "active_server_count": 0,
            "servers_with_expired_tokens": 0,
            "needs_reconnect": False,
        }
    return {
        "success": True,
        "ready": False,
        "site_registered": False,
        "user_registered": False,
        "has_mcp_servers": False,
        "message": _("AIDA is not configured on this site."),
    }


@frappe.whitelist(methods=["POST"])
def connect_aida_mcp_server(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_user_mcp_servers(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def reconnect_mcp_server(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["POST"])
def disconnect_mcp_server(*args, **kwargs):
    retired()
