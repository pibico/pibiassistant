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

import frappe


def is_chat_enabled() -> bool:
    """Return True when the PA Chat module is enabled.

    Reads `PA Core Settings.enable_pa_chat`. Cached for the
    duration of the request via `frappe.local`.

    Fail-safe: if the field/doctype isn't available yet — e.g. mid-migration,
    when upgrading from a PA build that predates `enable_pa_chat` — treat
    chat as OFF rather than raising. The transient result is NOT cached, so the
    real value is read once the schema is in place. This gate is a hot-path
    predicate (runs on every doc save via the wildcard dispatcher) and must
    never block a save or a migration.
    """
    cached = getattr(frappe.local, "_pa_chat_enabled", None)
    if cached is not None:
        return cached

    try:
        value = frappe.db.get_single_value("PA Core Settings", "enable_pa_chat")
    except Exception:
        # Field or DocType not present yet (migration in progress / older
        # schema). Off for now; don't cache so we re-read after migrate.
        return False

    enabled = bool(value)
    frappe.local._pa_chat_enabled = enabled
    return enabled


def clear_chat_gate_cache() -> None:
    """Drop the per-request cache. Call after toggling the gate."""
    if hasattr(frappe.local, "_pa_chat_enabled"):
        delattr(frappe.local, "_pa_chat_enabled")
