"""Token-authenticated upload endpoint behind the create_upload_link tool."""

import json

import frappe
from frappe import _

from pibiassistant.pibiassistant_chat.api._rate_limits import ip_only, rate_limit
from pibiassistant.plugins.core.tools.create_upload_link import TOKEN_TTL_SECONDS, token_digest, token_key
from pibiassistant.utils import attachments


def _consume(token: str) -> dict | None:
    """Single use: the first request that claims the token wins."""
    if not token or len(token) > 100:
        return None
    key = token_key(token)
    raw = frappe.cache().get_value(key)
    if not raw:
        return None
    claim = frappe.cache().make_key("pa_upload_claim:" + token_digest(token))
    if not frappe.cache().set(claim, "1", nx=True, ex=TOKEN_TTL_SECONDS):
        return None
    frappe.cache().delete_value(key)
    return json.loads(raw)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(ip_only, limit=20, seconds=60)
def upload_attachment(token: str | None = None) -> dict:
    state = _consume(token or "")
    if not state:
        frappe.throw(_("This upload link is invalid or has expired."), frappe.PermissionError)
    upload = frappe.request.files.get("file") if frappe.request else None
    if not upload:
        frappe.throw(_("No file was sent."), frappe.ValidationError)
    content = upload.stream.read(attachments.MAX_ATTACH_BYTES + 1)
    frappe.set_user(state["user"])
    try:
        file = attachments.attach_content(
            state["doctype"], state["docname"], upload.filename or "", content, is_private=state["is_private"]
        )
    except attachments.AttachmentError as e:
        frappe.throw(str(e), frappe.ValidationError)
    frappe.db.commit()
    return {"success": True, "file": file}
