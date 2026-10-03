"""Static catalogue of the supported direct providers."""

import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple

from .errors import ProviderConfigError

_OPENAI_RE = re.compile(r"^(gpt-|o\d|chatgpt-)")
_OPENAI_DROP = re.compile(
    r"embedding|whisper|tts|image|moderation|realtime|audio|transcribe|search|dall-e|davinci|babbage|computer-use|codex"
)
_GENERIC_DROP = re.compile(r"whisper|tts|embed|moderation|rerank")


def _openai_filter(entry):
    mid = str(entry.get("id") or "")
    return bool(_OPENAI_RE.match(mid)) and not _OPENAI_DROP.search(mid)


def _generic_filter(entry):
    mid = str(entry.get("id") or "").lower()
    if _GENERIC_DROP.search(mid):
        return False
    arch = entry.get("architecture")
    outs = arch.get("output_modalities") if isinstance(arch, dict) else None
    return not (outs and list(outs) != ["text"])


@dataclass(frozen=True)
class ProviderDef:
    id: str
    label: str
    wire: str  # "openai" | "anthropic" | "azure"
    base_url: str = ""
    base_url_required: bool = False
    key_required: bool = True
    base_url_presets: Tuple[Tuple[str, str], ...] = ()
    auth_header: str = "authorization"
    default_max_tokens: int = 4096
    console_url: str = ""
    models_path: str = "/models"
    suggested_models: Tuple[str, ...] = ()
    model_filter: Optional[Callable] = field(default=None, compare=False)


PROVIDER_DEFS = {
    d.id: d
    for d in (
        ProviderDef(
            "openai", "OpenAI", "openai", "https://api.openai.com/v1",
            default_max_tokens=8192, console_url="https://platform.openai.com/api-keys",
            model_filter=_openai_filter,
        ),
        ProviderDef(
            "anthropic", "Anthropic", "anthropic", "https://api.anthropic.com",
            auth_header="x-api-key", default_max_tokens=8192,
            console_url="https://console.anthropic.com/settings/keys", models_path="/v1/models",
            suggested_models=("claude-sonnet-5-5",),
        ),
        ProviderDef(
            "deepseek", "DeepSeek", "openai", "https://api.deepseek.com",
            default_max_tokens=4096, console_url="https://platform.deepseek.com/api_keys",
            suggested_models=("deepseek-flash", "deepseek-v4-pro"),
        ),
        ProviderDef(
            "qwen", "Qwen", "openai", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            base_url_presets=(
                ("International", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
                ("China", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            ),
            default_max_tokens=4096,
            console_url="https://modelstudio.console.alibabacloud.com/",
            suggested_models=("qwen-plus", "qwen-max"),
        ),
        ProviderDef(
            "xai", "xAI Grok", "openai", "https://api.x.ai/v1",
            default_max_tokens=8192, console_url="https://console.x.ai",
            models_path="/language-models", suggested_models=("grok-4.5",),
        ),
        ProviderDef(
            "azure_openai", "Azure OpenAI", "azure", "", base_url_required=True,
            auth_header="api-key", default_max_tokens=8192, console_url="https://portal.azure.com",
        ),
        ProviderDef(
            "openai_compatible", "OpenAI-compatible", "openai", "", base_url_required=True,
            key_required=False, default_max_tokens=4096,
            console_url="https://openrouter.ai/keys", model_filter=_generic_filter,
        ),
    )
}


def provider_def(provider_id):
    try:
        return PROVIDER_DEFS[provider_id]
    except KeyError:
        raise ProviderConfigError("Unknown provider type") from None


def filter_models(defn, entries):
    """Apply the provider's model filter to [{"id",...}] entries."""
    if not defn.model_filter:
        return list(entries)
    return [e for e in entries if defn.model_filter(e)]


def public_catalog():
    out = []
    for d in PROVIDER_DEFS.values():
        out.append(
            {
                "id": d.id,
                "label": d.label,
                "base_url": d.base_url,
                "base_url_required": d.base_url_required,
                "key_required": d.key_required,
                "presets": [{"label": a, "base_url": b} for a, b in d.base_url_presets],
                "console_url": d.console_url,
                "suggested_models": list(d.suggested_models),
            }
        )
    return out
