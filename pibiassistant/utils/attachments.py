"""Attach files to documents on behalf of MCP and AIDA clients.

Every path ends in `attach_content` or `attach_existing`, so size, type and permission rules
live in one place: the caller must be able to write to the target document.
"""

from __future__ import annotations

import base64
import binascii
import os
import re

import frappe
from frappe import _

MAX_ATTACH_BYTES = 10 * 1024 * 1024
MAX_BASE64_CHARS = (MAX_ATTACH_BYTES * 4) // 3 + 8
ALLOWED_EXTENSIONS = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".md", ".csv", ".json", ".xml", ".xls", ".xlsx", ".doc", ".docx", ".odt", ".ods"}
)
_MAGIC = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF8",),
    ".webp": (b"RIFF",),
    ".xlsx": (b"PK",),
    ".docx": (b"PK",),
}


class AttachmentError(Exception):
    """A request the user can fix: the message is safe to show."""


def clean_filename(name: str) -> str:
    base = os.path.basename(str(name or "").replace("\\", "/")).strip()
    base = re.sub(r"[^\w.\- ()]", "_", base)[:140].strip(" .")
    return base


def _check_name_and_type(filename: str) -> str:
    cleaned = clean_filename(filename)
    ext = os.path.splitext(cleaned)[1].lower()
    if not cleaned or ext not in ALLOWED_EXTENSIONS:
        raise AttachmentError(_("File type not allowed: {0}").format(ext or _("(none)")))
    return cleaned


def validate_content(filename: str, content: bytes) -> str:
    cleaned = _check_name_and_type(filename)
    if not content:
        raise AttachmentError(_("The file is empty."))
    if len(content) > MAX_ATTACH_BYTES:
        raise AttachmentError(_("The file is larger than {0} MB.").format(MAX_ATTACH_BYTES // (1024 * 1024)))
    magic = _MAGIC.get(os.path.splitext(cleaned)[1].lower())
    if magic and not content.startswith(magic):
        raise AttachmentError(_("The file content does not match its extension."))
    return cleaned


def decode_base64(data: str) -> bytes:
    text = re.sub(r"^data:[^,]*,", "", str(data or "")).strip()
    if len(text) > MAX_BASE64_CHARS:
        raise AttachmentError(_("The file is larger than {0} MB.").format(MAX_ATTACH_BYTES // (1024 * 1024)))
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        raise AttachmentError(_("The file content is not valid base64.")) from None


def check_target(doctype: str, name: str) -> None:
    if not doctype or not name or not frappe.db.exists("DocType", doctype) or not frappe.db.exists(doctype, name):
        raise AttachmentError(_("Document not found: {0} {1}").format(doctype, name))
    if not frappe.has_permission(doctype, "write", doc=name):
        raise AttachmentError(_("You do not have permission to attach files to {0} {1}.").format(doctype, name))


def _summary(file_doc) -> dict:
    return {
        "name": file_doc.name,
        "file_name": file_doc.file_name,
        "file_url": file_doc.file_url,
        "is_private": int(file_doc.is_private or 0),
        "attached_to_doctype": file_doc.attached_to_doctype,
        "attached_to_name": file_doc.attached_to_name,
    }


def attach_content(doctype: str, name: str, filename: str, content: bytes, is_private: bool = True) -> dict:
    check_target(doctype, name)
    cleaned = validate_content(filename, content)
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": cleaned,
            "attached_to_doctype": doctype,
            "attached_to_name": name,
            "content": content,
            "is_private": 1 if is_private else 0,
        }
    )
    file_doc.insert(ignore_permissions=True)
    return _summary(file_doc)


def attach_existing(doctype: str, name: str, file_url: str) -> dict:
    """Attach a file that is already stored in Frappe (for example one the user uploaded in the chat)."""
    check_target(doctype, name)
    url = str(file_url or "")
    if not url.startswith(("/files/", "/private/files/")) or ".." in url:
        raise AttachmentError(_("Only files stored in Frappe can be attached by URL."))
    source = frappe.db.get_value(
        "File", {"file_url": url}, ["name", "file_name", "is_private", "attached_to_doctype", "attached_to_name"], as_dict=True
    )
    if not source or not frappe.has_permission("File", "read", doc=source.name):
        raise AttachmentError(_("File not found: {0}").format(url))
    _check_name_and_type(source.file_name)
    already = frappe.db.get_value(
        "File", {"file_url": url, "attached_to_doctype": doctype, "attached_to_name": name}, "name"
    )
    if already:
        return _summary(frappe.get_doc("File", already))
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": source.file_name,
            "file_url": url,
            "attached_to_doctype": doctype,
            "attached_to_name": name,
            "is_private": source.is_private,
        }
    )
    file_doc.insert(ignore_permissions=True)
    return _summary(file_doc)
