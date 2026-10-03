# pibiAssistant - Desk boot info
# AGPL-3.0 License

"""Flags exposed to the Desk client through ``frappe.boot``."""


def boot_session(bootinfo):
    """Tell the Desk whether the native AIDA API is configured.

    In AIDA mode the discovery banner (an upsell for enabling PA Chat) is moot,
    so ``chat_banner.js`` reads this flag and skips its ``should_show_banner``
    request on every Desk load.
    """
    from pibiassistant.pibiassistant_chat.api.llm_config import llm_ready

    bootinfo.pa_aida_mode = 1 if llm_ready() else 0
