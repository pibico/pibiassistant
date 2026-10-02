# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Prompt templates (slash menu).

AIDA serves no remote prompt catalog, so the slash menu gets an empty list and
rendering a remote template answers "not available". The suggestion and pinning
endpoints were PA Cloud only and are retired.
"""

import frappe
from frappe import _

from pibiassistant.utils.retired import retired

# Prefix of the per-user prompt catalog cache. Local Prompt Template writes still call
# clear_prompt_catalog_cache(), which stays so those hooks keep working.
_CATALOG_CACHE_PREFIX = "pao_ar_prompt_catalog:"


def clear_prompt_catalog_cache():
    """Drop every user's cached prompt catalog."""
    frappe.cache.delete_keys(_CATALOG_CACHE_PREFIX)


@frappe.whitelist(methods=["GET"])
def get_suggested_prompts(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_prompt_templates():
    """Slash-menu templates. AIDA has no remote catalog, so the list is empty."""
    return {"templates": [], "categories": [], "pinned": []}


@frappe.whitelist(methods=["POST"])
def update_pinned_templates(*args, **kwargs):
    retired()


@frappe.whitelist(methods=["GET"])
def get_rendered_prompt(prompt_name: str, arguments: str | None = None):
    """Rendering a remote template is not available in AIDA."""
    if not prompt_name:
        return {"success": False, "error": _("prompt_name is required")}
    return {"success": False, "error": _("This feature is not available in AIDA mode.")}
