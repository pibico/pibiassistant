# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""Attach a file to an existing document (for example the source PDF of a purchase invoice)."""

import re
from typing import Any, Dict

import frappe
from frappe import _

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.query_errors import permission_error_result
from pibiassistant.utils import attachments


def normalize_base64(data: Any) -> str:
    """Accept MIME-wrapped, urlsafe and unpadded base64, which models and clients often emit."""
    text = re.sub(r"^data:[^,]*,", "", str(data or "")).strip()
    text = re.sub(r"\s+", "", text).replace("-", "+").replace("_", "/")
    return text + "=" * (-len(text) % 4)


class AttachFile(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "attach_file"
        self.description = (
            "Attach a file to an existing document so it shows in the document's attachments, e.g. the source PDF "
            "of a Purchase Invoice right after creating it. Give exactly one source: file_url of a file already stored "
            "in Frappe (the chat tells you the file_url of files the user uploaded), or content_base64 plus filename "
            "for a small file (max 10 MB; pdf, images, txt, csv, json, xml, office documents). If the client has the "
            "file only on disk, use create_upload_link instead. The user needs write permission on the document."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "DocType of the document, e.g. 'Purchase Invoice'."},
                "docname": {"type": "string", "description": "Name (id) of the document to attach the file to."},
                "file_url": {
                    "type": "string",
                    "description": "URL of a file already in Frappe, starting with /files/ or /private/files/.",
                },
                "content_base64": {"type": "string", "description": "File content, base64 encoded (small files only)."},
                "filename": {"type": "string", "description": "File name with extension; required with content_base64."},
                "is_private": {"type": "boolean", "default": True, "description": "Store the new file as private (default)."},
            },
            "required": ["doctype", "docname"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        docname = arguments.get("docname")
        file_url = arguments.get("file_url")
        content_b64 = arguments.get("content_base64")
        if bool(file_url) == bool(content_b64):
            return {"success": False, "error": "Provide exactly one of file_url or content_base64."}
        try:
            if file_url:
                file = attachments.attach_existing(doctype, docname, file_url)
            else:
                if not arguments.get("filename"):
                    return {"success": False, "error": "filename is required with content_base64."}
                file = attachments.attach_content(
                    doctype,
                    docname,
                    arguments["filename"],
                    attachments.decode_base64(normalize_base64(content_b64)),
                    is_private=arguments.get("is_private", True) is not False,
                )
        except attachments.AttachmentError as e:
            return {"success": False, "error": str(e)}
        except frappe.PermissionError as e:
            return permission_error_result(e, _("Permission denied."))
        return {"success": True, "file": file}


attach_file = AttachFile
