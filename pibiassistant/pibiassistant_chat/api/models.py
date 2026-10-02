# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""AI model listing and preference management."""

import frappe
from frappe import _

from ._helpers import (
    _aida_mode,
    _not_registered_error,
    _safe_error,
)


@frappe.whitelist(methods=["GET"])
def get_available_models():
    if _aida_mode():
        return _aida_models()
    return _get_available_models()


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


def _get_available_models():
    """
    Get available AI models from AR based on subscription tier.

    Uses the new streaming.list_available_models endpoint which supports
    per-request model selection. Model selection is now handled client-side
    via localStorage instead of server-side preferred model setting.

    Returns:
            dict: {
                    "success": bool,
                    "models": [...],
                    "max_tier_rank": float,
                    "default_model": str,
                    "auto_mode": {
                            "enabled": bool,
                            "description": str,
                            "model_id": "auto",
                            "fallback_chain_length": int
                    }
            }
    """
    try:
        from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

        client = get_pa_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.list_available_models(timeout=8)
        if not result:
            return {"error": _("Failed to fetch models")}

        # AR gates this endpoint on terms acceptance and answers with an
        # actionable error_code (TERMS_UPDATE_REQUIRED / TERMS_NOT_ACCEPTED)
        # instead of a model list. Pass the code through so the SPA can open
        # the terms flow rather than rendering an empty model picker.
        if result.get("error_code"):
            return {
                "error": result.get("error") or _("Models are unavailable right now."),
                "error_code": result["error_code"],
                "terms_url": result.get("terms_url"),
                "required_version": result.get("required_version"),
            }

        # Organize models by tier for the UI
        models = result.get("models", [])
        models_by_tier = {}
        for model in models:
            tier = model.get("tier", "Standard")
            if tier not in models_by_tier:
                models_by_tier[tier] = []
            models_by_tier[tier].append(model)

        return {
            "success": True,
            "models": models,
            "models_by_tier": models_by_tier,
            "max_tier_rank": result.get("max_tier_rank", 999),
            "default_model": result.get("default_model"),
            "auto_mode": result.get("auto_mode"),
        }

    except Exception as e:
        frappe.log_error(title="AIDA Models Error", message=f"Error getting models: {e!s}")
        return {"error": _safe_error(e, "AIDA Models Error")}


@frappe.whitelist(methods=["POST"])
def set_preferred_model(model_id: str | None = None):
    """
    Set the preferred AI model in AR.

    Args:
            model_id: Model ID to set as preferred

    Returns:
            dict: {"success": bool}
    """
    try:
        from pibiassistant.pibiassistant_chat.pa_cloud_client import get_pa_cloud_client

        client = get_pa_cloud_client()
        if not client:
            return {"success": _aida_mode()}

        success = client.set_preferred_model(model_id)

        if success:
            from pibiassistant.pibiassistant_chat.quota_cache import set_field

            set_field("preferred_model", model_id)

        return {"success": success}

    except Exception as e:
        frappe.log_error(title="AIDA Model Error", message=f"Error setting model: {e!s}")
        return {"success": False, "error": _safe_error(e, "AIDA Model Error")}
