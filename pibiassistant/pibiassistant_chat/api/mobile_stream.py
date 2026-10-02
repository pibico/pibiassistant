# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Mobile API — session helper for Socket.IO auth."""


import frappe
from frappe import _
from frappe.query_builder.functions import Count, Max, Min
from werkzeug import Response

from pibiassistant.utils.retired import retired

from ._helpers import _safe_error


def _assert_mobile_oauth_request() -> None:
    """AIDA-M5: refuse ``create_web_session`` unless the caller authenticated
    via an OAuth Bearer Token issued to a AIDA Mobile OAuth client.

    The bridge plants browser cookies from a bearer token — any client not
    issued via the mobile dynamic-registration flow (``api.auth:755``) has no
    business minting browser sessions. API keys, session cookies, and the AR
    integration client are refused.
    """
    header = frappe.get_request_header("Authorization", "") or ""
    if not header.lower().startswith("bearer "):
        frappe.throw(
            _("create_web_session requires OAuth Bearer authentication"),
            frappe.AuthenticationError,
        )
    access_token = header.split(None, 1)[1].strip()
    if not access_token:
        frappe.throw(_("Missing bearer token"), frappe.AuthenticationError)

    client_name = frappe.db.get_value(
        "OAuth Bearer Token",
        {"access_token": access_token, "status": "Active"},
        "client",
    )
    if not client_name:
        frappe.throw(_("Invalid bearer token"), frappe.AuthenticationError)

    # AIDA Mobile clients are registered with ``app_name = "AIDA Mobile"``
    # by ``api.auth:791``. The cloud integration client uses
    # ``app_name = "AIDA Cloud"``, which is correctly rejected.
    app_name = frappe.db.get_value("OAuth Client", client_name, "app_name")
    if app_name != "AIDA Mobile":
        frappe.throw(
            _("This OAuth client is not allowed to use create_web_session"),
            frappe.PermissionError,
        )


def _cookie_bridge_page(cookies: dict, redirect_to: str) -> str:
    """HTML that sets each prepared cookie on the real origin, then redirects.

    Every value reaches the script as a JSON string literal, never raw text:
    cookies carry user-controlled data (full_name, user_image) and a stray quote
    or ``</script>`` would otherwise break the bridge or inject script.
    """
    import json as _json
    from urllib.parse import quote

    cookie_lines = []
    for key, opts in cookies.items():
        value = quote((opts.get("value") or "").encode("utf-8"))
        max_age = opts.get("max_age") or ""
        # AIDA-M5: SameSite=Strict neutralizes cross-site request forgery if
        # the planted cookie ever leaks to a third-party context. The mobile
        # WebView navigates same-origin after this bridge, so Strict is safe.
        cookie = f"{key}={value}; path=/; SameSite=Strict; Secure" + (f"; max-age={max_age}" if max_age else "")
        cookie_lines.append(f"document.cookie = {_json.dumps(cookie)};")

    # json.dumps emits a correctly-escaped JS string literal; "</" is split so
    # the literal can never close the inline <script> element.
    cookies_js = "\n".join(cookie_lines).replace("</", "<\\/")
    safe_redirect_js = _json.dumps(redirect_to).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html><head><script>
{cookies_js}
window.location.replace({safe_redirect_js});
</script></head><body></body></html>"""


@frappe.whitelist(methods=["GET"])
def create_web_session() -> Response:
    """Create a browser session from a Bearer token and redirect.

    Uses GET: the mobile WebView reaches this via a top-level page navigation,
    which can only issue GET. CSRF is a non-concern — the caller is authenticated
    solely by the OAuth Bearer header (cross-checked to a AIDA Mobile client in
    ``_assert_mobile_oauth_request``); no ambient cookie is trusted on the way in.

    Mobile WebView calls this URL with Authorization header. The response
    uses Frappe's LoginManager to create a full session, then returns an
    HTML page that sets all session cookies via document.cookie and redirects
    to the target page. This avoids iOS WebView issues where Set-Cookie
    headers on 3xx responses are not persisted.

    Query params:
            redirect_to (str): The Frappe page to open after auth (e.g. /app/sales-order/SO-001)
    """
    redirect_to = frappe.form_dict.get("redirect_to") or "/app"
    user = frappe.session.user

    if user == "Guest":
        frappe.throw(_("Authentication required"), frappe.AuthenticationError)

    # AIDA-M5: the bearer-to-cookie bridge is meant for the mobile WebView,
    # not generic API tokens. Require the request to have been authenticated
    # via an OAuth Bearer Token (not API key / session cookie) and cross-check
    # the token's client against the allow-list of known mobile OAuth clients.
    _assert_mobile_oauth_request()

    # SECURITY: Only allow same-site absolute paths. Reject scheme URIs
    # (javascript:, data:, http://evil.example/...) and protocol-relative URLs
    # (//evil.example). This runs before the value is inlined into a <script>.
    if not redirect_to.startswith("/") or redirect_to.startswith("//"):
        redirect_to = "/app"

    # Use Frappe's official LoginManager — runs hooks, creates session, sets all cookies
    login_manager = frappe.auth.LoginManager()
    login_manager.login_as(user)

    page = _cookie_bridge_page(frappe.local.cookie_manager.cookies, redirect_to)

    return Response(page, status=200, content_type="text/html")


@frappe.whitelist(methods=["GET"])
def download_file_by_token(file_url: str | None = None) -> Response:
    """Serve private file content authenticated via Bearer token.

    Mobile clients can't use cookie-based file access due to iOS CSRF issues
    (SFSafariViewController sets cookies in the shared jar, triggering CSRF checks).
    This endpoint validates Bearer token auth and returns the raw file content.

    Args:
            file_url (str): The private file URL, e.g. /private/files/document.pdf
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required"), frappe.AuthenticationError)

    if not file_url:
        frappe.throw(_("file_url is required"))

    import os

    # Look up the File doc via its file_url — do NOT derive a disk path from
    # user input. Then delegate the authorization decision to the File doctype,
    # which respects is_private + the attached_to_doctype ownership chain.
    file_doc_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not file_doc_name:
        frappe.throw(_("File not found"), frappe.DoesNotExistError)

    file_doc = frappe.get_doc("File", file_doc_name)
    file_doc.check_permission("read")

    # Only after the permission check, resolve the real on-disk path.
    file_path = file_doc.get_full_path()

    if not os.path.exists(file_path):
        frappe.throw(_("File not found"), frappe.DoesNotExistError)

    # file_path comes from a permission-checked File doc (check_permission above) —
    # the caller's file_url is never used to build the path.
    with open(file_path, "rb") as f:  # nosemgrep: frappe-security-file-traversal
        content = f.read()

    return _file_response(content, os.path.basename(file_path), file_url)


_INLINE_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf")


def _file_response(content: bytes, filename: str, file_url: str) -> Response:
    """Serve bytes inline only for safe previewable types; everything else downloads.

    Uploaded HTML/SVG served inline from the site origin would run script with the
    user's session, so those are forced to attachment and sniffing is disabled.
    """
    import mimetypes

    content_type = mimetypes.guess_type(file_url)[0] or "application/octet-stream"
    disposition = "inline" if content_type in _INLINE_TYPES else "attachment"
    safe_name = "".join(c for c in filename if c not in '"\\\r\n')
    return Response(
        content,
        status=200,
        content_type=content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@frappe.whitelist(methods=["GET"])
def get_socket_session() -> dict:
    """Return the current session ID so mobile clients can authenticate Socket.IO.

    Frappe's socket server uses the `sid` cookie to identify users. Mobile apps
    can't share cookies between fetch() and socket.io-client, so this endpoint
    returns the sid value explicitly.
    """
    return {
        "sid": frappe.session.sid,
        "user": frappe.session.user,
        "site_name": frappe.local.site,
    }










# ============================================================================
# Additional Mobile-Specific Endpoints
# ============================================================================


@frappe.whitelist(methods=["GET"])
def get_sessions(limit: int = 50, offset: int = 0) -> dict:
    """
    Get user's chat sessions for mobile conversation history.

    Optimized for mobile with pagination support.

    Args:
            limit: Maximum sessions to return (default 50, max 100)
            offset: Pagination offset

    Returns:
            dict: {sessions: [...], has_more: bool}
    """
    try:
        user = frappe.session.user
        limit = min(int(limit), 100)
        offset = int(offset)

        # Get session summaries using Frappe Query Builder
        PAChatMessage = frappe.qb.DocType("PA Chat Message")

        session_query = (
            frappe.qb.from_(PAChatMessage)
            .select(
                PAChatMessage.session_id,
                Min(PAChatMessage.creation).as_("started"),
                Max(PAChatMessage.creation).as_("last_activity"),
                Count("*").as_("message_count"),
            )
            .where(PAChatMessage.user == user)
            .groupby(PAChatMessage.session_id)
            .orderby("last_activity", order=frappe.qb.desc)
            .limit(limit + 1)
            .offset(offset)
        )
        sessions = session_query.run(as_dict=True)

        has_more = len(sessions) > limit
        if has_more:
            sessions = sessions[:limit]

        # Fetch the first user message for each session as a preview
        session_ids = [s["session_id"] for s in sessions]
        previews: dict[str, str] = {}
        if session_ids:
            first_messages = frappe.get_all(
                "PA Chat Message",
                filters={
                    "session_id": ["in", session_ids],
                    "user": user,
                    "role": "user",
                },
                fields=["session_id", "content"],
                order_by="creation asc",
            )
            # Keep only the first message per session
            for msg in first_messages:
                if msg.session_id not in previews:
                    content = (msg.content or "")[:100]
                    previews[msg.session_id] = content + ("..." if len(msg.content or "") > 100 else "")

        for session in sessions:
            session["preview"] = previews.get(session["session_id"], _("New conversation"))

        return {"sessions": sessions, "has_more": has_more}

    except Exception as e:
        frappe.log_error(title="AIDA Mobile Sessions Error", message=f"Error getting mobile sessions: {e!s}")
        return {"sessions": [], "has_more": False, "error": _safe_error(e, "AIDA Mobile Sessions Error")}


@frappe.whitelist(methods=["GET"])
def get_messages(session_id: str, limit: int = 100, offset: int = 0) -> dict:
    """
    Get messages for a session.

    Optimized for mobile with pagination.

    Args:
            session_id: The session ID
            limit: Maximum messages to return
            offset: Pagination offset

    Returns:
            dict: {messages: [...], has_more: bool}
    """
    try:
        user = frappe.session.user
        limit = min(int(limit), 500)
        offset = int(offset)

        # Ownership check — session_id is client-supplied and MUST be verified
        # against the caller's own messages to prevent cross-user IDOR.
        if not frappe.db.exists("PA Chat Message", {"session_id": session_id, "user": user}):
            frappe.throw(_("Session not found"), frappe.PermissionError)

        messages = frappe.get_all(
            "PA Chat Message",
            filters={"session_id": session_id, "user": user},
            fields=["name", "role", "content", "creation", "model", "credits_used", "routing"],
            order_by="creation asc",
            limit_page_length=limit + 1,
            limit_start=offset,
        )

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        # Format messages for mobile
        formatted = []
        for msg in messages:
            metadata = None
            # A zero-credit turn — cached, errored, or a free model — still has
            # a receipt worth showing. The old guard returned None and dropped it.
            if msg.model or msg.credits_used or msg.routing:
                metadata = {
                    "model": msg.model,
                    "credits_used": msg.credits_used,
                    "routing": msg.routing,
                }

            formatted.append(
                {
                    "id": msg.name,
                    "role": msg.role,
                    "content": msg.content or "",
                    "timestamp": str(msg.creation),
                    "metadata": metadata,
                }
            )

        return {"messages": formatted, "has_more": has_more}

    except frappe.PermissionError:
        # Surface as 403 instead of burying in a generic error payload
        raise
    except Exception as e:
        frappe.log_error(title="AIDA Mobile Messages Error", message=f"Error getting mobile messages: {e!s}")
        return {"messages": [], "has_more": False, "error": _safe_error(e, "AIDA Mobile Messages Error")}


@frappe.whitelist(methods=["GET"])
def search_sessions(query: str, limit: int = 20) -> list:
    """
    Search chat sessions by message content.

    Args:
            query: Search query string
            limit: Maximum results (default 20)

    Returns:
            list: Matching sessions with preview, message_count, match_context
    """
    try:
        user = frappe.session.user
        limit = min(int(limit), 50)

        if not query or len(query) < 2:
            return []

        # AIDA-M12: cap query length and neutralize LIKE wildcards. A
        # megabyte-scale query would force a pathological scan of every
        # AIDA Message row the user owns, and ``%``/``_`` are promoted into
        # SQL wildcards by frappe.get_all — escape them so search matches
        # the user's literal intent.
        query = str(query)[:200]
        safe_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

        # Find messages matching the query
        matching_messages = frappe.get_all(
            "PA Chat Message",
            filters={
                "user": user,
                "content": ["like", f"%{safe_query}%"],
            },
            fields=["session_id", "content", "creation"],
            order_by="creation desc",
        )

        # Deduplicate by session_id, keeping the first (most recent) match
        seen_sessions: set[str] = set()
        unique_matches: list[dict] = []
        for msg in matching_messages:
            if msg.session_id not in seen_sessions:
                seen_sessions.add(msg.session_id)
                unique_matches.append(msg)
            if len(unique_matches) >= limit:
                break

        if not unique_matches:
            return []

        session_ids = [m["session_id"] for m in unique_matches]

        # Get session metadata (last_activity + message_count) via Query Builder
        PAChatMessage = frappe.qb.DocType("PA Chat Message")
        session_stats = (
            frappe.qb.from_(PAChatMessage)
            .select(
                PAChatMessage.session_id,
                Max(PAChatMessage.creation).as_("last_activity"),
                Count("*").as_("message_count"),
            )
            .where((PAChatMessage.user == user) & (PAChatMessage.session_id.isin(session_ids)))
            .groupby(PAChatMessage.session_id)
        ).run(as_dict=True)

        stats_map: dict[str, dict] = {s["session_id"]: s for s in session_stats}

        # Get first user message per session for preview
        first_messages = frappe.get_all(
            "PA Chat Message",
            filters={
                "session_id": ["in", session_ids],
                "user": user,
                "role": "user",
            },
            fields=["session_id", "content"],
            order_by="creation asc",
        )
        preview_map: dict[str, str] = {}
        for msg in first_messages:
            if msg.session_id not in preview_map:
                content = (msg.content or "")[:100]
                preview_map[msg.session_id] = content + ("..." if len(msg.content or "") > 100 else "")

        # Build results with match context
        formatted = []
        for match in unique_matches:
            sid = match["session_id"]
            stats = stats_map.get(sid, {})
            preview = preview_map.get(sid, _("Conversation"))

            # Extract context around the match
            matched_content = (match.get("content") or "")[:200]
            match_context = None
            if matched_content:
                query_lower = query.lower()
                content_lower = matched_content.lower()
                pos = content_lower.find(query_lower)
                if pos >= 0:
                    start = max(0, pos - 30)
                    end = min(len(matched_content), pos + len(query) + 50)
                    match_context = matched_content[start:end]

            formatted.append(
                {
                    "session_id": sid,
                    "preview": preview,
                    "last_activity": stats.get("last_activity"),
                    "message_count": stats.get("message_count", 0),
                    "match_context": match_context,
                }
            )

        # Sort by last_activity descending
        formatted.sort(key=lambda x: x.get("last_activity") or "", reverse=True)
        return formatted

    except Exception as e:
        frappe.log_error(title="AIDA Mobile Search Error", message=f"Error searching sessions: {e!s}")
        return []


@frappe.whitelist(methods=["POST"])
def stream_chat(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_available_models(*args, **kwargs):
    retired()
