"""Checks shared by the document-lifecycle tools (cancel, amend, create-from, assign, comment)."""

from typing import Any, Dict, Optional

import frappe


def access_error(doctype: str, name: str, perm_type: str) -> Optional[Dict[str, Any]]:
    """The tool result to return when the DocType is closed to this action at the PA layer, else None."""
    from pibiassistant.core.security_config import validate_document_access

    result = validate_document_access(user=frappe.session.user, doctype=doctype, name=name or "", perm_type=perm_type)
    return None if result.get("success") else result


def fail(message: str, **extra) -> Dict[str, Any]:
    return {"success": False, "error": message, **extra}


def document_url(doctype: str, name: str) -> str:
    return frappe.utils.get_url_to_form(doctype, name)


MAX_PDF_BYTES = 15 * 1024 * 1024


def print_pdf(doctype: str, name: str, print_format: Optional[str] = None, letterhead: bool = True):
    """(pdf bytes, print format used) for a document the caller may read and print; ValueError when it cannot be."""
    from frappe.utils.pdf import get_pdf

    if not doctype or not name or not frappe.db.exists("DocType", doctype) or not frappe.db.exists(doctype, name):
        raise ValueError(f"{doctype} '{name}' not found")
    doc = frappe.get_doc(doctype, name)
    if not frappe.has_permission(doctype, "read", doc=doc) or not frappe.has_permission(doctype, "print", doc=doc):
        raise ValueError(f"You do not have permission to print {doctype} '{name}'.")
    meta = frappe.get_meta(doctype)
    if print_format:
        known = frappe.get_all("Print Format", filters={"doc_type": doctype, "disabled": 0}, pluck="name")
        if print_format not in known and print_format != "Standard":
            options = ", ".join(known[:10]) or "none besides Standard"
            raise ValueError(f"Print format '{print_format}' does not exist for {doctype}. Available: {options}.")
    used = print_format or meta.default_print_format or "Standard"
    html = frappe.get_print(doctype, name, print_format=None if used == "Standard" else used, doc=doc, no_letterhead=0 if letterhead else 1)
    pdf = get_pdf(html)
    if not pdf or not pdf.startswith(b"%PDF"):
        raise ValueError(f"Could not render {doctype} '{name}' as PDF.")
    if len(pdf) > MAX_PDF_BYTES:
        raise ValueError("The PDF is larger than 15 MB.")
    return pdf, used


def save_private_file(filename: str, content: bytes) -> Dict[str, Any]:
    """Store ``content`` as a private File owned by the caller, replacing an earlier file of the same name."""
    for old in frappe.get_all("File", filters={"file_name": filename, "is_private": 1, "owner": frappe.session.user, "attached_to_doctype": ["is", "not set"]}, pluck="name"):
        frappe.delete_doc("File", old, force=True, ignore_permissions=True)
    file_doc = frappe.get_doc({"doctype": "File", "file_name": filename, "content": content, "is_private": 1})
    file_doc.save(ignore_permissions=True)
    return {"file_url": file_doc.file_url, "file_name": filename, "file_size": len(content), "download_link": f"[{filename}]({file_doc.file_url})"}
