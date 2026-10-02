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
            "The email is queued for delivery using the site's SMTP settings."
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

        try:
            frappe.sendmail(
                recipients=recipients,
                cc=cc or None,
                subject=subject,
                message=message,
                delayed=True,
            )
            return {
                "success": True,
                "message": _("Email queued to {0} recipient(s)").format(len(recipients)),
                "recipients": recipients,
                "subject": subject,
            }
        except Exception as e:
            log_failure("Send Email Tool Error", e)
            return {"success": False, "error": str(e)[:2000]}
