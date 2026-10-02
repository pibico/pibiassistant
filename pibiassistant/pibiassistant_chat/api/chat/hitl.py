"""HITL pause inspection — the AIDA pending approval.

Called by the chat frontend on ``ChatView`` mount, on socket reconnect,
and from the widget's init() so it can re-render the InteractionCard
after the user stepped away or the socket dropped.
"""

import frappe


@frappe.whitelist(methods=["GET"])
def get_pending_interrupt(session_id: str) -> dict:
    """Return the AIDA pending approval, or ``{pending: False}`` so the frontend
    hydration path degrades silently — the user can still type a new message."""
    from .._helpers import _validate_session_id

    _validate_session_id(session_id)

    from .aida_stream import is_aida_mode

    if is_aida_mode():
        from .aida_tools import pending_payload

        return pending_payload(session_id, frappe.session.user)

    # Not in AIDA mode: no assistant to hydrate from.
    return {"pending": False}
