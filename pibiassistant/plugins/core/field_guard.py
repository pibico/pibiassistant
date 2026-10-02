"""Field guards shared by the document tools."""

from typing import Any, Dict, Iterable, Optional, Set

# Never writable through the tools: docstatus changes go through submit/cancel tools,
# the rest are audit columns the framework maintains.
SYSTEM_FIELDS = frozenset({"docstatus", "owner", "creation", "modified", "modified_by"})
UPDATE_ONLY_BLOCKED = frozenset({"name", "doctype", "parent", "parenttype", "parentfield"})


def check_field_names(meta: Any, keys: Iterable[str], *, creating: bool) -> Optional[Dict[str, Any]]:
    """Return an error dict when `keys` hold system columns or fields the doctype lacks."""
    blocked = SYSTEM_FIELDS if creating else SYSTEM_FIELDS | UPDATE_ONLY_BLOCKED
    keys = list(keys)

    system = [k for k in keys if k in blocked]
    if system:
        hint = (
            " Use submit_document to submit or cancel a document."
            if "docstatus" in system
            else ""
        )
        return {
            "success": False,
            "error": f"Cannot set system fields: {', '.join(system)}.{hint}",
            "error_type": "system_field",
            "fields": system,
        }

    valid = set(meta.get_valid_columns())
    unknown = [k for k in keys if k not in valid and not meta.has_field(k) and not (creating and k == "name")]
    if unknown:
        return {
            "success": False,
            "error": f"Unknown fields for {meta.name}: {', '.join(unknown)}. Use get_doctype_info for valid fieldnames.",
            "error_type": "unknown_field",
            "fields": unknown,
        }
    return None


def restricted_fields_for_doctype(doctype: str, user_role: str) -> Set[str]:
    """SENSITIVE_FIELDS for everyone, plus ADMIN_ONLY_FIELDS when the role is PA User.

    A "*" admin-only entry (whole doctype restricted) adds no field names; callers that
    must refuse the whole doctype check for it themselves.
    """
    from pibiassistant.core.security_config import ADMIN_ONLY_FIELDS, SENSITIVE_FIELDS

    restricted: Set[str] = set(SENSITIVE_FIELDS.get("all_doctypes", []))
    restricted.update(SENSITIVE_FIELDS.get(doctype, []))

    if user_role == "PA User":
        restricted.update(ADMIN_ONLY_FIELDS.get("all_doctypes", []))
        doctype_admin_fields = ADMIN_ONLY_FIELDS.get(doctype, [])
        if doctype_admin_fields != "*":
            restricted.update(doctype_admin_fields)
    return restricted
