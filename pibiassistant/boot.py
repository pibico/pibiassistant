# pibiAssistant - Desk boot info
# AGPL-3.0 License

"""Flags exposed to the Desk client through ``frappe.boot``."""


def boot_session(bootinfo):
    """Tell the Desk whether the native AIDA API is configured.

    In AIDA mode the discovery banner (an upsell for enabling PA Chat) is moot,
    so ``chat_banner.js`` reads this flag and skips its ``should_show_banner``
    request on every Desk load.
    """
    from pibiassistant.pibiassistant_chat.aida_mode import is_aida_mode

    bootinfo.pa_aida_mode = 1 if is_aida_mode() else 0
