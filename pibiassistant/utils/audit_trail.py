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

import json
from typing import Any, Dict, Optional

import frappe
from frappe.utils import now

# Allowed values for PA Audit Log `status` — must match the DocType Select.
AUDIT_STATUS_SUCCESS = "Success"
AUDIT_STATUS_ERROR = "Error"
AUDIT_STATUS_TIMEOUT = "Timeout"
AUDIT_STATUS_PERMISSION_DENIED = "Permission Denied"
_VALID_STATUSES = {
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_TIMEOUT,
    AUDIT_STATUS_PERMISSION_DENIED,
}

# Output data is stored as JSON text in a Code field; cap to keep audit rows
# from bloating when a tool returns a large payload.
_OUTPUT_DATA_MAX_BYTES = 50_000


def _sanitize_arguments(arguments: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Defensive sanitization at the audit sink — callers are expected to
    sanitize too, but this ensures secrets never land in the table even
    when a non-BaseTool call site forgets.

    Uses the same _is_sensitive_key heuristic as BaseTool so token-count
    metrics (input_tokens / output_tokens / total_tokens) are preserved while
    credential-shaped keys still get redacted.
    """
    if not isinstance(arguments, dict):
        return arguments
    from pibiassistant.core.base_tool import redact_sensitive

    return redact_sensitive(arguments)


def log_tool_execution(
    tool_name: str,
    user: str,
    arguments: Optional[Dict[str, Any]],
    status: str,
    execution_time: float,
    source_app: Optional[str] = None,
    error_message: Optional[str] = None,
    error_type: Optional[str] = None,
    traceback_str: Optional[str] = None,
    output_data: Optional[Any] = None,
):
    """
    Log tool execution for comprehensive audit trail.

    Args:
        tool_name: Name of the executed tool
        user: User who executed the tool
        arguments: Tool arguments (sensitive data should be pre-sanitized; the
            sink re-sanitizes defensively)
        status: One of "Success", "Error", "Timeout", "Permission Denied".
            Unknown values are coerced to "Error" with a warning.
        execution_time: Time taken in seconds
        source_app: App that provides the tool
        error_message: Error message if execution failed
        error_type: Exception class name or semantic category (e.g.
            "PermissionError", "ValidationError", "ToolReportedError")
        traceback_str: Full Python traceback (exception paths only)
        output_data: Tool output data for audit trail
    """
    try:
        if status not in _VALID_STATUSES:
            frappe.logger("audit_trail").warning(
                f"log_tool_execution: invalid status {status!r} for tool {tool_name}; coercing to 'Error'"
            )
            status = AUDIT_STATUS_ERROR

        sanitized_arguments = _sanitize_arguments(arguments)

        # Extract target information from arguments (after sanitization so we
        # can't leak secrets via target fields either)
        target_doctype = None
        target_name = None
        if isinstance(sanitized_arguments, dict):
            target_doctype = sanitized_arguments.get("doctype")
            target_name = sanitized_arguments.get("name")

        # Serialize output for storage, clamp oversized payloads
        output_data_str, output_truncated = _serialize_for_audit(output_data)

        input_data_str = None
        if sanitized_arguments is not None:
            try:
                input_data_str = json.dumps(sanitized_arguments, default=str)
            except (TypeError, ValueError):
                input_data_str = str(sanitized_arguments)[:_OUTPUT_DATA_MAX_BYTES]

        audit_doc = frappe.get_doc(
            {
                "doctype": "PA Audit Log",
                "action": tool_name,
                "tool_name": tool_name,
                "user": user,
                "status": status,
                "timestamp": now(),
                "execution_time": execution_time,
                "target_doctype": target_doctype,
                "target_name": target_name,
                "client_id": getattr(frappe.local, "assistant_client_id", None),
                "session_id": getattr(frappe.local, "assistant_session_id", None),
                "source_app": source_app,
                "ip_address": getattr(frappe.local, "request_ip", None),
                "input_data": input_data_str,
                "output_data": output_data_str,
                "output_truncated": 1 if output_truncated else 0,
                "error_message": error_message,
                "error_type": error_type,
                "traceback": traceback_str,
            }
        )

        audit_doc.insert(ignore_permissions=True)

    except Exception as e:
        # Don't fail tool execution due to audit logging issues
        frappe.logger("audit_trail").warning(f"Failed to log tool execution: {str(e)}")


def _serialize_for_audit(output_data: Any) -> tuple:
    """Serialize tool output for the audit row. Returns (json_str_or_none, truncated_bool)."""
    if output_data is None:
        return None, False
    try:
        serialized = json.dumps(output_data, default=str)
    except (TypeError, ValueError):
        serialized = str(output_data)
    if len(serialized) > _OUTPUT_DATA_MAX_BYTES:
        return serialized[:_OUTPUT_DATA_MAX_BYTES], True
    return serialized, False



