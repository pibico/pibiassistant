# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""One-time upload link so a client that has the file on disk can attach it without sending its bytes through the model."""

import hashlib
import json
import secrets
from typing import Any, Dict

import frappe

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.utils import attachments

TOKEN_TTL_SECONDS = 900


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_key(token: str) -> str:
    return "pa_upload_token:" + token_digest(token)


class CreateUploadLink(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "create_upload_link"
        self.description = (
            "Get a one-time upload URL (valid 15 minutes, one file, max 10 MB) that attaches a file to an existing "
            "document. Use it when the file lives on the client's disk (e.g. Claude Code): run the returned curl "
            "command, replacing the path, right after creating the document. Prefer attach_file when the file is "
            "already stored in Frappe."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "DocType of the document, e.g. 'Purchase Invoice'."},
                "docname": {"type": "string", "description": "Name (id) of the document to attach the file to."},
                "is_private": {"type": "boolean", "default": True},
            },
            "required": ["doctype", "docname"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype, docname = arguments.get("doctype"), arguments.get("docname")
        try:
            attachments.check_target(doctype, docname)
        except attachments.AttachmentError as e:
            return {"success": False, "error": str(e)}
        token = secrets.token_urlsafe(32)
        state = {
            "user": frappe.session.user,
            "doctype": doctype,
            "docname": docname,
            "is_private": arguments.get("is_private", True) is not False,
        }
        frappe.cache().set_value(token_key(token), json.dumps(state), expires_in_sec=TOKEN_TTL_SECONDS)
        url = frappe.utils.get_url("/api/method/pibiassistant.api.mcp_upload.upload_attachment")
        return {
            "success": True,
            "upload_url": f"{url}?token={token}",
            "method": "POST (multipart/form-data, field 'file')",
            "curl": f"curl -sS -F file=@/path/to/file '{url}?token={token}'",
            "expires_in_seconds": TOKEN_TTL_SECONDS,
            "max_bytes": attachments.MAX_ATTACH_BYTES,
            "allowed_extensions": sorted(attachments.ALLOWED_EXTENSIONS),
        }


create_upload_link = CreateUploadLink
