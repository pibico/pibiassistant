"""Common adapter behaviour: key handling, URLs, timeouts, test()."""

import time

from frappe import _

from . import http, urlsafe
from .errors import ProviderConfigError, ProviderError, ProviderNetworkError

MAX_MODELS = 500


class BaseAdapter:
    def __init__(self, row, defn, key=None):
        self.row = dict(row or {})
        self.defn = defn
        self.slug = self.row.get("slug") or defn.id.replace("_", "-")
        self.label = self.row.get("label") or defn.label
        self._api_key = key  # never exposed; None means "fetch lazily"

    def __repr__(self):
        return f"<{type(self).__name__} {self.slug}>"

    def __getstate__(self):
        raise TypeError("provider adapters cannot be serialized")

    # -- helpers -----------------------------------------------------------
    def _ctx(self):
        return {"provider": self.slug, "label": self.label}

    def _row_info(self):
        return {"slug": self.slug, "provider_id": self.defn.id, "label": self.label}

    def _key(self):
        if self._api_key is not None:
            return self._api_key
        try:
            from ...llm_config import get_provider_key

            return get_provider_key(self.row.get("name")) or ""
        except Exception:
            return ""

    def _need_key(self):
        key = self._key()
        if self.defn.key_required and not key:
            raise ProviderConfigError(_("Enter the API key"), **self._ctx())
        return key

    def _base(self):
        base = (self.row.get("base_url") or self.defn.base_url or "").strip()
        if not base:
            raise ProviderConfigError(_("The base URL is not valid"), **self._ctx())
        try:
            return urlsafe.validate_base_url(base, resolve=False)["url"]
        except ProviderError as e:
            e.provider, e.label = self.slug, self.label
            raise

    def _timeout(self, model, stream):
        if stream:
            return (10, 60)
        read = http.clamp_timeout(self.row.get("timeout_seconds"))
        if self.defn.id in ("xai", "deepseek") or self._is_reasoning(model or ""):
            read = max(read, 300)
        return (10, read)

    def _is_reasoning(self, model):
        return False

    def _model(self, model):
        model = (model or self.row.get("default_model") or "").strip()
        if not model:
            raise ProviderConfigError(_("Enter the default model"), **self._ctx())
        return model

    def _max_tokens(self, max_tokens, model):
        mt = int(max_tokens or self.row.get("max_output_tokens") or 0) or self.defn.default_max_tokens
        if not max_tokens and self._is_reasoning(model):
            mt = max(mt, 8192)
        return mt

    # -- interface ---------------------------------------------------------
    def list_models(self):
        raise NotImplementedError

    def chat(self, messages, tools=None, model=None, max_tokens=None, cancel=None, **_ignored):
        raise NotImplementedError

    def stream_chat(self, messages, tools=None, model=None, max_tokens=None, cancel=None):
        raise NotImplementedError

    def _test_impl(self):
        """Return (detail suffix, models list)."""
        models = self.list_models()
        return f" - {len(models)} models", models

    def test(self):
        t0 = time.monotonic()
        out = {"ok": False, "detail": "", "error": "", "latency_ms": 0, "models": []}
        try:
            self._need_key()
            v = urlsafe.validate_base_url(
                (self.row.get("base_url") or self.defn.base_url or "").strip(), resolve=False
            )
            suffix, models = self._test_impl()
            out.update(ok=True, detail=f"{v['scheme']}://{v['host']}{suffix}", models=models)
        except ProviderError as e:
            e.provider, e.label = e.provider or self.slug, e.label or self.label
            out["error"] = e.user_message()
        except Exception:
            out["error"] = ProviderNetworkError(**self._ctx()).user_message()
        out["latency_ms"] = int((time.monotonic() - t0) * 1000)
        return out
