"""Direct LLM providers (OpenAI, Anthropic, DeepSeek, Qwen, xAI, Azure OpenAI, OpenAI-compatible)."""

from .errors import (  # noqa: F401
    ProviderAuthError,
    ProviderCancelled,
    ProviderConfigError,
    ProviderContentFilterError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderNetworkError,
    ProviderNotFoundError,
    ProviderOverloadedError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderUnsupportedError,
    log_provider_error,
)
from .registry import PROVIDER_DEFS, ProviderDef, provider_def, public_catalog  # noqa: F401
from .urlsafe import validate_base_url  # noqa: F401


def get_provider(row, key=None):
    """Build the adapter for a provider row (dict from llm_config.llm_providers()).

    key=None makes the adapter fetch the decrypted key lazily inside each call.
    """
    from .anthropic import AnthropicAdapter
    from .openai_compat import (
        AzureOpenAIAdapter,
        DeepSeekAdapter,
        GenericAdapter,
        OpenAIAdapter,
        QwenAdapter,
        XAIAdapter,
    )

    classes = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "deepseek": DeepSeekAdapter,
        "qwen": QwenAdapter,
        "xai": XAIAdapter,
        "azure_openai": AzureOpenAIAdapter,
        "openai_compatible": GenericAdapter,
    }
    pid = (row or {}).get("provider_id")
    cls = classes.get(pid)
    if cls is None:
        raise ProviderConfigError("Unknown provider type", provider=str(pid or ""))
    return cls(row, provider_def(pid), key=key)
