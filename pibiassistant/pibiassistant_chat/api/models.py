# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""AI model listing (set_preferred_model is retired)."""

import frappe
from frappe import _

from pibiassistant.utils.retired import retired

from ._helpers import _aida_mode


@frappe.whitelist(methods=["GET"])
def get_available_models(refresh=0):
    from .llm_config import backend_mode

    if backend_mode() == "aida":
        if _aida_mode():
            return _aida_models()
        return {"error": _("This feature is not available in AIDA mode.")}
    return _mixed_models(refresh)


def _mixed_models(refresh):
    """Direct and both modes: AIDA models (when allowed) followed by the direct providers' models."""
    from frappe.utils import cint

    from ..aida_mode import is_aida_mode
    from .llm_config import direct_models, mode_allows_aida, mode_allows_direct

    if not _aida_mode():
        return {"error": _("No AI provider is configured. Ask your administrator to set it up in PA Core Settings.")}
    models = []
    error = None
    if mode_allows_aida() and is_aida_mode():
        result = _aida_models()
        models += result.get("models") or []
        if not result.get("success"):
            error = result.get("error")
    if mode_allows_direct():
        models += direct_models(refresh=bool(cint(refresh)))
    if not models:
        return {"success": False, "models": [], "error": error or _("Models are unavailable right now.")}
    return {
        "success": True,
        "models": models,
        "models_by_tier": {"Standard": models},
        "max_tier_rank": 999,
        "default_model": None,
        "auto_mode": {
            "enabled": True,
            "description": _("Default model"),
            "model_id": "auto",
            "fallback_chain_length": 0,
        },
    }


def _aida_models():
    """AIDA mode: model list from the AIDA API. model_id is "provider/model"."""
    from .aida import get_models

    result = get_models() or {}
    if not result.get("providers"):
        return {"success": False, "models": [], "error": result.get("error") or _("Models are unavailable right now.")}
    models = []
    for provider, info in (result.get("providers") or {}).items():
        if not info.get("available", True):
            continue
        for name in info.get("models") or []:
            if "embedding" in name:
                continue
            models.append(
                {
                    "model_id": f"{provider}/{name}",
                    "display_name": name,
                    "provider": provider,
                    "tier": "Standard",
                    "tier_rank": 1,
                }
            )
    return {
        "success": True,
        "models": models,
        "models_by_tier": {"Standard": models} if models else {},
        "max_tier_rank": 999,
        "default_model": None,
        "auto_mode": {
            "enabled": True,
            "description": _("Default AIDA model"),
            "model_id": "auto",
            "fallback_chain_length": 0,
        },
    }


@frappe.whitelist(methods=["POST"])
def set_preferred_model(*args, **kwargs):
    retired()
