# pibiAssistant - LLM backend configuration (AIDA gateway and direct providers)
# AGPL-3.0 License

"""Single reader of the direct-provider table plus the backend-mode decisions.

Import-light on purpose (frappe and stdlib; the providers package is imported
lazily). Every function swallows its own failures and degrades to the AIDA-only
behaviour, so a site whose database has not been migrated for the
``PA LLM Provider`` table behaves exactly as before.
"""

from __future__ import annotations

import re

import frappe
from frappe import _

from .. import aida_mode as _aida_mode_mod

# configured models come first in provider_models(); the live listing can hold hundreds
PICKER_MAX_PER_PROVIDER = 100
PROVIDER_TABLE = "PA LLM Provider"
_PROVIDERS_KEY = "pa_llm_providers"
_PROVIDERS_TTL = 300
_MODELS_TTL = 600
_MODELS_STALE_TTL = 24 * 3600
_HEALTH_TTL = 45
_ID_MAX = 200
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,140}$")

_FALLBACK_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "deepseek": "DeepSeek",
    "qwen": "Qwen",
    "xai": "xAI Grok",
    "azure_openai": "Azure OpenAI",
    "openai_compatible": "OpenAI-compatible",
}

_ROW_FIELDS = [
    "name",
    "idx",
    "provider_id",
    "slug",
    "label",
    "enabled",
    "base_url",
    "default_model",
    "extra_models",
    "api_version",
    "deployment",
    "timeout_seconds",
    "max_output_tokens",
    "supports_tools",
]


# -- reader ------------------------------------------------------------------


def _registry_label(provider_id: str) -> str:
    try:
        from .chat.providers.registry import provider_def

        return provider_def(provider_id).label
    except Exception:
        return _FALLBACK_LABELS.get(provider_id) or provider_id or ""


def _keyed_names(names: list[str]) -> set[str]:
    """Names of the rows that have a stored key (names only, never key material)."""
    if not names:
        return set()
    try:
        rows = frappe.db.sql(
            "select `name` from `__Auth` where `doctype`=%s and `fieldname`=%s and `name` in %s",
            (PROVIDER_TABLE, "api_key", tuple(names)),
        )
        return {r[0] for r in rows}
    except Exception:
        return set()


def _build_rows() -> list[dict]:
    raw = frappe.get_all(
        PROVIDER_TABLE,
        filters={"parent": "PA Core Settings", "parenttype": "PA Core Settings", "parentfield": "llm_providers"},
        fields=_ROW_FIELDS,
        order_by="idx asc",
    )
    keyed = _keyed_names([r["name"] for r in raw])
    rows = []
    for r in raw:
        pid = (r.get("provider_id") or "").strip()
        slug = (r.get("slug") or "").strip() or pid.replace("_", "-")
        extra = [m.strip() for m in (r.get("extra_models") or "").splitlines() if m.strip()]
        try:
            timeout = int(r.get("timeout_seconds") or 120)
        except (TypeError, ValueError):
            timeout = 120
        rows.append(
            {
                "name": r["name"],
                "idx": int(r.get("idx") or 0),
                "provider_id": pid,
                "slug": slug,
                "label": (r.get("label") or "").strip() or _registry_label(pid),
                "enabled": bool(r.get("enabled")),
                "base_url": (r.get("base_url") or "").strip(),
                "default_model": (r.get("default_model") or "").strip(),
                "extra_models": extra,
                "api_version": (r.get("api_version") or "").strip(),
                "deployment": (r.get("deployment") or "").strip(),
                "timeout_seconds": timeout,
                "max_output_tokens": int(r.get("max_output_tokens") or 0),
                "supports_tools": bool(r.get("supports_tools")),
                "has_key": r["name"] in keyed,
            }
        )
    seen: dict[str, int] = {}
    for row in rows:
        seen[row["label"]] = seen.get(row["label"], 0) + 1
    for row in rows:
        if seen[row["label"]] > 1:
            row["label"] = f"{row['label']} ({row['slug']})"
    return rows


def llm_providers(enabled_only: bool = False) -> list[dict]:
    """THE reader of the provider table: [] when the table is missing or anything fails."""
    try:
        if not frappe.db.table_exists(PROVIDER_TABLE):
            return []
        cache = frappe.cache()
        rows = cache.get_value(_PROVIDERS_KEY, expires=True)
        if rows is None:
            rows = _build_rows()
            cache.set_value(_PROVIDERS_KEY, rows, expires_in_sec=_PROVIDERS_TTL)
        return [dict(r) for r in rows if r.get("enabled") or not enabled_only]
    except Exception:
        return []


def get_provider_key(row_name: str) -> str:
    """The stored key of a provider row. INTERNAL: only providers/* and this module call it."""
    from frappe.utils.password import get_decrypted_password

    return get_decrypted_password(PROVIDER_TABLE, row_name, "api_key", raise_exception=False) or ""


def prepared_provider_test(row: dict):
    """Fetch the key now (caller's thread) and return a zero-arg callable that runs the connection test."""
    from .chat.providers import get_provider
    from .chat.providers.urlsafe import allow_private_now, allow_private_scope

    adapter = get_provider(row, key=get_provider_key(row["name"]))
    # frappe.conf is not available in the pool threads: capture the flag here
    return allow_private_scope(allow_private_now(), adapter.test)


def display_label(row: dict) -> str:
    return row.get("label") or _registry_label(row.get("provider_id") or "")


# -- modes -------------------------------------------------------------------


def _settings():
    return frappe.get_cached_doc("PA Core Settings")


def backend_mode() -> str:
    try:
        value = _settings().get("llm_backend_mode")
    except Exception:
        return "aida"
    return {"Direct providers": "direct", "Both": "both"}.get(value, "aida")


def mode_allows_aida() -> bool:
    return backend_mode() in ("aida", "both")


def provider_usable(row: dict) -> bool:
    if not row.get("enabled"):
        return False
    pid = row.get("provider_id")
    if pid == "azure_openai":
        return bool(
            row.get("has_key") and row.get("base_url") and (row.get("deployment") or row.get("extra_models"))
        )
    if pid == "openai_compatible":
        return bool(row.get("has_key") or row.get("base_url"))
    return bool(row.get("has_key"))


def usable_providers() -> list[dict]:
    return [r for r in llm_providers(enabled_only=True) if provider_usable(r)]


def mode_allows_direct() -> bool:
    if backend_mode() not in ("direct", "both"):
        return False
    return bool(usable_providers())


def llm_ready() -> bool:
    """The chat gate: AIDA key set (modes aida/both) or at least one usable direct provider."""
    if backend_mode() == "aida":
        return bool(_aida_mode_mod.is_aida_mode())
    return (mode_allows_aida() and bool(_aida_mode_mod.is_aida_mode())) or mode_allows_direct()


def provider_by_slug(slug: str, usable_only: bool = True) -> dict | None:
    for row in llm_providers(enabled_only=usable_only):
        if row["slug"] == slug and (not usable_only or provider_usable(row)):
            return row
    return None


def provider_by_name(row_name: str) -> dict | None:
    for row in llm_providers():
        if row["name"] == row_name:
            return row
    return None


# -- model ids ---------------------------------------------------------------


def parse_model_id(model_id) -> tuple[str, str, str]:
    """(kind, provider, model); kind is auto, aida or direct. Pure."""
    chosen = str(model_id or "").strip()[:_ID_MAX]
    if not chosen or chosen == "auto":
        return ("auto", "", "")
    if chosen.startswith("d:"):
        slug, sep, model = chosen[2:].partition("/")
        if sep and slug and model:
            return ("direct", slug, model)
        return ("auto", "", "")
    if "/" in chosen:
        prov, model = chosen.split("/", 1)
        return ("aida", prov, model)
    return ("aida", "", chosen)


def default_direct_model(row: dict) -> str:
    extra = row.get("extra_models") or []
    return row.get("default_model") or row.get("deployment") or (extra[0] if extra else "") or ""


def _aida_defaults() -> tuple[str, str]:
    try:
        s = _settings()
        return (s.get("aida_default_provider") or ""), (s.get("aida_default_model") or "")
    except Exception:
        return "", ""


def default_backend_choice() -> tuple[str, str, str]:
    if mode_allows_aida() and _aida_mode_mod.is_aida_mode():
        prov, model = _aida_defaults()
        return ("aida", prov, model)
    if mode_allows_direct():
        usable = usable_providers()
        for row in usable:
            model = default_direct_model(row)
            if model:
                return ("direct", row["slug"], model)
        if usable:
            return ("direct", usable[0]["slug"], "")
    return ("none", "", "")


def resolve_backend(model_id) -> tuple[str, str, str]:
    kind, prov, mdl = _resolve(model_id)
    if kind == "direct" and not mdl:
        return ("none", "", "")
    return (kind, prov, mdl)


def _resolve(model_id) -> tuple[str, str, str]:
    kind, prov, mdl = parse_model_id(model_id)
    if kind == "auto":
        return default_backend_choice()
    if kind == "direct":
        row = provider_by_slug(prov) if mode_allows_direct() else None
        if row is None:
            return default_backend_choice()
        mdl = mdl or default_direct_model(row)
        return ("direct", prov, mdl) if mdl else ("none", "", "")
    if mode_allows_aida() and _aida_mode_mod.is_aida_mode():
        return ("aida", prov, mdl)
    return default_backend_choice()


# -- listings ----------------------------------------------------------------


def _models_key(row_name: str) -> str:
    return f"pa_llm_models:{row_name}"


def _stale_key(row_name: str) -> str:
    return f"pa_llm_models_stale:{row_name}"


def _health_key(row_name: str) -> str:
    return f"pa_llm_health:{row_name}"


def provider_models(row: dict) -> list[dict]:
    """Configured models first, then the cached live listing. No network."""
    ids: list[str] = []
    for m in [row.get("default_model"), row.get("deployment"), *(row.get("extra_models") or [])]:
        if m and m not in ids:
            ids.append(m)
    try:
        cache = frappe.cache()
        live = cache.get_value(_models_key(row["name"]), expires=True) or cache.get_value(_stale_key(row["name"]), expires=True) or []
    except Exception:
        live = []
    labels = {}
    for m in live:
        if isinstance(m, dict) and m.get("id"):
            labels[m["id"]] = m.get("label") or m["id"]
            if m["id"] not in ids:
                ids.append(m["id"])
    return [{"id": i, "label": labels.get(i, i)} for i in ids]


def _apply_filter(row: dict, models: list[dict]) -> list[dict]:
    try:
        from .chat.providers.registry import provider_def

        flt = provider_def(row["provider_id"]).model_filter
    except Exception:
        return models
    if flt is None:
        return models
    # The registry filter takes the listing entry (a dict with at least "id").
    return [m for m in models if flt(m)] if callable(flt) else models


def refresh_provider_models(row_name: str) -> list:
    """Live listing of one row (network); provider errors propagate so the settings button can show them."""
    try:
        row = provider_by_name(row_name)
        if row is None:
            return []
        from .chat.providers import get_provider

        listed = get_provider(row).list_models()
    except Exception as exc:
        if exc.__class__.__module__.startswith("pibiassistant.pibiassistant_chat.api.chat.providers"):
            raise
        return []
    models = _apply_filter(row, [m for m in listed if isinstance(m, dict) and m.get("id")])
    cache = frappe.cache()
    cache.set_value(_models_key(row_name), models, expires_in_sec=_MODELS_TTL)
    cache.set_value(_stale_key(row_name), models, expires_in_sec=_MODELS_STALE_TTL)
    return models


def refresh_direct_models() -> None:
    """Background job: list every usable row, remembering failures briefly so the picker does not re-enqueue."""
    for row in usable_providers():
        try:
            refresh_provider_models(row["name"])
        except Exception:
            try:
                frappe.cache().set_value(_models_key(row["name"]), [], expires_in_sec=_MODELS_TTL)
            except Exception:
                pass


def direct_models(refresh: bool = False) -> list[dict]:
    """Model picker entries of the usable direct providers (grouped by ``provider``)."""
    entries = []
    missing = False
    for row in usable_providers():
        try:
            if refresh:
                try:
                    refresh_provider_models(row["name"])
                except Exception:
                    pass
            elif frappe.cache().get_value(_models_key(row["name"]), expires=True) is None:
                missing = True
            label = display_label(row)
            group = _("{0} (direct)").format(label)
            for m in provider_models(row)[:PICKER_MAX_PER_PROVIDER]:
                entries.append(
                    {
                        "model_id": f"d:{row['slug']}/{m['id']}",
                        "display_name": m["id"],
                        "provider": group,
                        "provider_label": label,
                        "backend": "direct",
                        "tier": "Standard",
                        "tier_rank": 1,
                    }
                )
        except Exception:
            continue
    if missing:
        try:
            frappe.enqueue(
                "pibiassistant.pibiassistant_chat.api.llm_config.refresh_direct_models",
                queue="short",
                job_id=f"pa_llm_models_refresh:{frappe.local.site}",
                deduplicate=True,
            )
        except Exception:
            pass
    return entries


def invalidate_llm_cache(doc=None, method=None) -> None:
    """doc_events hook of PA Core Settings: drop the provider and per-row caches."""
    try:
        cache = frappe.cache()
        names = set()
        for row in cache.get_value(_PROVIDERS_KEY, expires=True) or []:
            names.add(row.get("name"))
        try:
            if frappe.db.table_exists(PROVIDER_TABLE):
                names.update(frappe.get_all(PROVIDER_TABLE, filters={"parenttype": "PA Core Settings"}, pluck="name"))
        except Exception:
            pass
        cache.delete_value(_PROVIDERS_KEY)
        for name in filter(None, names):
            for key in (_models_key(name), _stale_key(name), _health_key(name)):
                cache.delete_value(key)
    except Exception:
        pass


def store_provider_health(row_name: str, result: dict) -> None:
    try:
        frappe.cache().set_value(_health_key(row_name), result, expires_in_sec=_HEALTH_TTL)
    except Exception:
        pass


def cached_provider_health(row_name: str):
    try:
        return frappe.cache().get_value(_health_key(row_name), expires=True)
    except Exception:
        return None


def cached_provider_status() -> dict:
    """{"<Label> API": last result} from the health cache. No network."""
    out = {}
    try:
        for row in llm_providers(enabled_only=True):
            cached = cached_provider_health(row["name"])
            if cached:
                out[f"{display_label(row)} API"] = cached
    except Exception:
        pass
    return out


def valid_row_name(name) -> bool:
    return isinstance(name, str) and bool(_NAME_RE.match(name))
