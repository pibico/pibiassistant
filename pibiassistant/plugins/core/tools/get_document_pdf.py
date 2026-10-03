# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""PDF of a document with its print format, as a private downloadable file."""

import re
from typing import Any, Dict

import frappe

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.core.doc_actions import fail, print_pdf, save_private_file
from pibiassistant.plugins.query_errors import log_failure


class DocumentPdf(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "get_document_pdf"
        self.description = (
            "Render an existing document (invoice, quotation, order, delivery note...) as a PDF with its official "
            "print format and letterhead, and return a download link. Use this when the user asks for the PDF/print "
            "of a document; generate_document is only for free-form Markdown reports. Optional print_format (name of "
            "a Print Format for that DocType; omit for the default). Copy the returned download_link verbatim. "
            "The file is private to the user."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "DocType of the document (e.g. 'Sales Invoice')"},
                "name": {"type": "string", "description": "Name/ID of the document"},
                "print_format": {"type": "string", "description": "Print Format name (optional, default format if omitted)"},
                "letterhead": {"type": "boolean", "default": True, "description": "Include the company letterhead"},
            },
            "required": ["doctype", "name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype, name = arguments.get("doctype"), arguments.get("name")
        try:
            pdf, used = print_pdf(doctype, name, arguments.get("print_format"), arguments.get("letterhead", True) is not False)
            safe = re.sub(r"[^\w.\-]+", "_", f"{doctype}-{name}")[:120]
            saved = save_private_file(f"{safe}.pdf", pdf)
            frappe.db.commit()
            return {
                "success": True, "doctype": doctype, "name": name, "print_format": used, **saved,
                "message": f"PDF of {doctype} '{name}' ready. Copy this markdown link VERBATIM into your answer: {saved['download_link']}",
            }
        except ValueError as e:
            return fail(str(e), doctype=doctype, name=name)
        except Exception as e:
            frappe.db.rollback()
            log_failure("Document PDF Error", e)
            return fail(str(e) or f"Could not render {doctype} '{name}'", doctype=doctype, name=name)


document_pdf = DocumentPdf
