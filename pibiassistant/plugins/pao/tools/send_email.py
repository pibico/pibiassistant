# pibiAssistant - Send Email Tool
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

"""
Send Email Tool — queues email via the site's configured Email Account.

Invoked by AR Workflow email nodes via MCP, ensuring emails originate
from the client's domain/SMTP rather than the AR platform.
"""

from typing import Any

import frappe
from frappe import _

from frappe.utils import validate_email_address

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.query_errors import log_failure

MAX_RECIPIENTS = 50
MAX_ATTACHED_DOCUMENTS = 3


def preview(arguments: dict[str, Any]) -> str:
    recipients = arguments.get("recipients") or []
    recipients = [recipients] if isinstance(recipients, str) else [r for r in recipients if isinstance(r, str)]
    docs = [f"{d.get('doctype')} {d.get('name')}" for d in (arguments.get("attach_documents") or []) if isinstance(d, dict)]
    text = f"Send an email to {', '.join(recipients[:5])}{' and others' if len(recipients) > 5 else ''}: \"{str(arguments.get('subject') or '')[:100]}\"."
    return text + (f" Attaches the PDF of {', '.join(docs)}." if docs else "")


class SendEmail(BaseTool):
    """
    MCP tool that sends email using the Frappe site's configured Email Account.

    Queues the email via ``frappe.sendmail()`` (EmailQueue) so delivery
    is asynchronous and uses the site owner's SMTP configuration.
    """

    def __init__(self):
        super().__init__()
        self.name = "send_email"
        self.description = (
            "Send an email from the Frappe site's configured email account. "
            "Use this when a workflow or agent needs to notify someone by email. "
            "The email is queued for delivery using the site's SMTP settings. To send an invoice, quotation or any "
            "document by email, pass it in attach_documents: it is attached as a PDF with its print format. "
            "Needs the user's approval."
        )
        self.source_app = "pibiassistant"
        self.category = "Communication"
        self.requires_permission = None

        self.inputSchema = {
            "type": "object",
            "properties": {
                "recipients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of recipient email addresses.",
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional CC recipient email addresses.",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line.",
                },
                "message": {
                    "type": "string",
                    "description": "Email body content (HTML or plain text).",
                },
                "send_as_html": {
                    "type": "boolean",
                    "default": True,
                    "description": "If true, the message is sent as HTML. If false, plain text.",
                },
                "attach_documents": {
                    "type": "array",
                    "maxItems": MAX_ATTACHED_DOCUMENTS,
                    "description": (
                        "Documents to attach as PDF with their print format, e.g. the invoice being sent. "
                        "Each needs permission to read and print it. Up to 3."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "doctype": {"type": "string"},
                            "name": {"type": "string"},
                            "print_format": {"type": "string", "description": "Optional Print Format name"},
                        },
                        "required": ["doctype", "name"],
                    },
                },
            },
            "required": ["recipients", "subject", "message"],
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Queue email via frappe.sendmail() using the site's Email Account."""
        if not frappe.has_permission("Communication", "create"):
            return {"success": False, "error": _("You do not have permission to send email.")}

        recipients = arguments.get("recipients") or []
        cc = arguments.get("cc") or []
        if isinstance(recipients, str):
            recipients = [recipients]
        if isinstance(cc, str):
            cc = [cc]
        subject = arguments.get("subject", "")
        message = arguments.get("message", "")

        if not recipients:
            return {"success": False, "error": _("No recipients provided")}

        if not subject.strip():
            return {"success": False, "error": _("Subject cannot be empty")}

        if not message.strip():
            return {"success": False, "error": _("Message body cannot be empty")}

        # Filter out empty strings
        recipients = [r.strip() for r in recipients if isinstance(r, str) and r.strip()]
        cc = [r.strip() for r in cc if isinstance(r, str) and r.strip()]

        if not recipients:
            return {"success": False, "error": _("No valid recipients after filtering")}

        if len(recipients) + len(cc) > MAX_RECIPIENTS:
            return {
                "success": False,
                "error": _("Too many recipients: the limit is {0} per email.").format(MAX_RECIPIENTS),
            }

        invalid = [r for r in recipients + cc if not validate_email_address(r, throw=False)]
        if invalid:
            return {
                "success": False,
                "error": _("Invalid email address(es): {0}").format(", ".join(invalid)),
                "invalid_recipients": invalid,
            }

        attachments = []
        attached = arguments.get("attach_documents") or []
        if attached:
            if not isinstance(attached, list) or len(attached) > MAX_ATTACHED_DOCUMENTS:
                return {"success": False, "error": _("At most {0} documents can be attached.").format(MAX_ATTACHED_DOCUMENTS)}
            from pibiassistant.plugins.core.doc_actions import print_pdf

            total = 0
            for item in attached:
                if not isinstance(item, dict):
                    return {"success": False, "error": _("Each attached document needs a doctype and a name.")}
                try:
                    pdf, _used = print_pdf(item.get("doctype"), item.get("name"), item.get("print_format"))
                except ValueError as e:
                    return {"success": False, "error": str(e)}
                total += len(pdf)
                if total > 15 * 1024 * 1024:
                    return {"success": False, "error": _("The attachments are larger than 15 MB.")}
                safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in f"{item['doctype']}-{item['name']}")[:120]
                attachments.append({"fname": f"{safe}.pdf", "fcontent": pdf})

        try:
            frappe.sendmail(
                recipients=recipients,
                cc=cc or None,
                subject=subject,
                message=message,
                attachments=attachments or None,
                delayed=True,
            )
            return {
                "success": True,
                "message": _("Email queued to {0} recipient(s)").format(len(recipients)),
                "recipients": recipients,
                "subject": subject,
                "attachments": [a["fname"] for a in attachments],
            }
        except Exception as e:
            log_failure("Send Email Tool Error", e)
            return {"success": False, "error": str(e)[:2000]}
