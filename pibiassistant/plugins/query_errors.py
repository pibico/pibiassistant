"""Map client-caused query/save failures to friendly messages so they are not logged as server errors."""

from typing import Any, Dict, Optional

import frappe
from frappe import _
from frappe.utils import strip_html

try:
    from pymysql.err import DataError, InterfaceError, OperationalError, ProgrammingError

    DB_ERRORS = (OperationalError, ProgrammingError, DataError, InterfaceError)
except ImportError:  # pragma: no cover
    DB_ERRORS = ()

# MariaDB rejects bad dates and out-of-range numbers with these codes, whatever pymysql class carries them.
VALUE_ERROR_CODES = {1264, 1265, 1292, 1366, 1367}


def _db_error_code(exc: Exception) -> Optional[int]:
    code = exc.args[0] if exc.args else None
    return code if isinstance(code, int) else None


USER_ERRORS = (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError)


def client_error_message(exc: Exception) -> Optional[str]:
    """Friendly text when `exc` is the caller's fault (bad field, filter, missing data), else None."""
    try:
        if frappe.db.is_missing_column(exc):
            return _("A field or filter names a column that does not exist on this DocType. Check the field names with get_doctype_info.")
    except Exception:
        pass
    if DB_ERRORS and isinstance(exc, DB_ERRORS) and _db_error_code(exc) in VALUE_ERROR_CODES:
        frappe.logger("pibiassistant").warning("Database data error mapped to message: %s", exc)
        return _("A date or number value has an invalid format or is out of range. Dates must be real calendar dates written YYYY-MM-DD (datetimes YYYY-MM-DD HH:MM:SS); numbers must be plain digits.")
    if DB_ERRORS and isinstance(exc, DB_ERRORS):
        # Raw driver text carries the schema name and SQL fragments; keep it server side.
        frappe.logger("pibiassistant").warning("Database error mapped to generic message: %s", exc)
        return _("The query could not be run: a filter, field or value is not valid for this DocType. Check names and value formats with get_doctype_info.")
    if isinstance(exc, frappe.MandatoryError):
        return _("Missing required fields: {0}").format(strip_html(str(exc)))
    if isinstance(exc, frappe.DoesNotExistError):
        return _("Not found: {0}").format(strip_html(str(exc)))
    if isinstance(exc, (frappe.ValidationError, frappe.PermissionError)):
        return strip_html(str(exc)) or type(exc).__name__
    return None


def log_failure(title: str, exc: Exception) -> None:
    """Log server-side failures with a short groupable title; user mistakes are not errors."""
    if isinstance(exc, USER_ERRORS):
        return
    frappe.log_error(title=title[:140], message=str(exc)[:2000])


def strip_schema(text: str) -> str:
    """Drop the database name from driver text such as "Table '_db.tabX' doesn't exist"."""
    schema = getattr(frappe.conf, "db_name", None)
    text = str(text)
    if schema:
        text = text.replace(f"`{schema}`.", "").replace(f"{schema}.", "").replace(schema, "database")
    return text


def single_doctype_message(doctype: Any) -> Optional[str]:
    """Message for a Single DocType, which has no rows to list or search; None otherwise."""
    if not doctype or not isinstance(doctype, str):
        return None
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return None
    if meta.issingle:
        return _("{0} is a Single DocType: it has one record and no list. Use get_document with doctype and name '{0}' instead.").format(doctype)
    return None


def permission_error_result(exc: Exception, fallback: str, **extra: Any) -> Dict[str, Any]:
    """Standard tool payload for a PermissionError; `fallback` is used when the exception has no text."""
    message = strip_html(str(exc)) or fallback
    return {"success": False, "error": message, "error_type": "permission_error", **extra}
