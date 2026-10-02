# pibiAssistant - AIDA mode check
# AGPL-3.0 License

"""Import-light AIDA-mode check shared by the API helpers and the PA Cloud client."""


def is_aida_mode() -> bool:
    """True when the native AIDA API key is set (PA Cloud is never used)."""
    try:
        from frappe.utils.password import get_decrypted_password

        return bool(
            get_decrypted_password(
                "PA Core Settings", "PA Core Settings", "aida_api_key", raise_exception=False
            )
        )
    except Exception:
        return False
