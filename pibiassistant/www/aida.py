import csv
import os
import re

import frappe
import frappe.sessions
import frappe.utils

from pibiassistant.pibiassistant_chat.api._helpers import _aida_mode
from pibiassistant.pibiassistant_chat.gate import is_chat_enabled
from pibiassistant.pibiassistant_chat.utils.security_headers import apply_spa_headers
from pibiassistant.utils.asset_versions import module_import_map

no_cache = 1


def get_context(context):
    """
    Context provider for the pibiAssistant AIDA Vue.js frontend
    """
    # Runtime gate: when PA Chat is disabled the SPA route returns 404.
    # The route itself is registered unconditionally so toggling chat on
    # makes it live immediately without a worker restart.
    if not is_chat_enabled():
        raise frappe.PageDoesNotExistError

    # Security: CSP, X-Frame-Options, Referrer-Policy for the SPA shell.
    # Applied to all /aida/* routes since conversations.py and
    # settings.py re-export this get_context unchanged.
    apply_spa_headers()

    # Require authentication
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    csrf_token = frappe.sessions.get_csrf_token()
    # CSRF token is generated lazily and must be persisted before the page
    # renders, otherwise subsequent POSTs from the SPA fail validation.
    frappe.db.commit()  # nosemgrep: frappe-manual-commit

    context = frappe._dict()
    context.csrf_token = csrf_token
    context.boot = get_boot()
    context.asset_version = get_asset_version()
    context.import_map = {"imports": module_import_map("aida/js")}
    return context


@frappe.whitelist(methods=["POST"])
def get_context_for_dev():
    """Development mode context for hot reload.

    AIDA-M4: previously allowed ``allow_guest=True`` behind a
    ``developer_mode`` gate. Misconfigured staging/prod often leaves
    ``developer_mode=1`` on, which would expose ``get_boot()`` (csrf_token,
    socketio port, session user) to unauthenticated callers. The boot
    payload is already only useful for logged-in users during Vite HMR, so
    requiring session auth closes the hole without affecting the intended
    workflow.
    """
    if not frappe.conf.developer_mode:
        frappe.throw(frappe._("This method is only meant for developer mode"))
    return get_boot()


def get_boot():
    """
    Get boot data for the frontend
    """
    # Get user's theme preference (Dark / Light / Automatic)
    user_theme = frappe.db.get_value("User", frappe.session.user, "desk_theme") or "Light"
    theme_map = {"Dark": "dark", "Light": "light", "Automatic": "automatic"}
    theme = theme_map.get(user_theme, "light")

    lang = str(frappe.local.lang or "en")
    bootinfo = {
        "site_name": str(frappe.local.site),
        "user": str(frappe.session.user),
        "csrf_token": str(frappe.sessions.get_csrf_token()),
        "lang": lang,
        "aida_lang": lang,
        "aida_messages": get_messages(lang),
        "theme": theme,
        "socketio_port": frappe.conf.get("socketio_port") or 9000,
        "aida_mode": _aida_mode(),
        "aida_tz": _system_timezone(),
        "can_use": _can_use_aida(),
    }

    # Get user's full name for display
    user_info = (
        frappe.db.get_value("User", frappe.session.user, ["full_name", "user_image"], as_dict=True) or {}
    )
    bootinfo["user_fullname"] = user_info.get("full_name") or frappe.session.user
    bootinfo["user_image"] = user_info.get("user_image") or ""

    return bootinfo


def _system_timezone():
    try:
        return frappe.utils.get_system_timezone()
    except Exception:
        return "UTC"


def _can_use_aida():
    """Same verdict the chat endpoints enforce, so the SPA can show a no-access screen up front."""
    try:
        from pibiassistant.pibiassistant_chat.api.settings.access import can_use_pao

        return bool(can_use_pao().get("can_use"))
    except Exception:
        frappe.log_error(title="AIDA boot can_use check failed")
        return True


_LANG_RE = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})?$")


def _read_csv(path):
    out = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) >= 2 and row[0] and row[1] and row[0] != row[1]:
                out[row[0]] = row[1]
    return out


_SPA_LITERAL_RE = re.compile(r"""\b__\(\s*(?:"((?:[^"\\\n]|\\.)*)"|'((?:[^'\\\n]|\\.)*)')""")
_JS_ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}
# Keys the SPA passes to __() through a variable (js/lib/greeting.js partOfDay).
_SPA_DYNAMIC_KEYS = ("Good morning", "Good afternoon", "Good evening")


def _unescape_js(text):
    return re.sub(r"\\(.)", lambda m: _JS_ESCAPES.get(m.group(1), m.group(1)), text)


def _spa_keys():
    """Source strings the SPA can look up: __("...") literals under public/aida/js plus the dynamic ones."""
    root = frappe.get_app_path("pibiassistant", "public", "aida", "js")
    paths = []
    for folder, _dirs, names in os.walk(root):
        paths.extend(os.path.join(folder, n) for n in names if n.endswith(".js"))
    paths.sort()
    key = "aida_spa_keys:" + str(max((int(os.path.getmtime(p)) for p in paths), default=0)) + f":{len(paths)}"
    cache = frappe.cache()
    keys = cache.get_value(key)
    if keys is None:
        found = set(_SPA_DYNAMIC_KEYS)
        for path in paths:
            with open(path, encoding="utf-8") as fh:
                for dq, sq in _SPA_LITERAL_RE.findall(fh.read()):
                    found.add(_unescape_js(dq or sq))
        keys = sorted(found)
        cache.set_value(key, keys)
    return set(keys)


def get_messages(lang):
    """{English source: translation} for `lang` limited to what the SPA uses, base language first (es-AR -> es)."""
    lang = str(lang or "en").replace("_", "-")
    if not _LANG_RE.match(lang) or lang.split("-")[0].lower() == "en":
        return {}
    base = frappe.get_app_path("pibiassistant", "translations")
    files = []
    for code in dict.fromkeys([lang.split("-")[0], lang]):
        for name in (code, code.lower()):
            path = os.path.join(base, name + ".csv")
            if os.path.isfile(path) and path not in files:
                files.append(path)
    if not files:
        return {}
    key = "aida_messages_spa:" + lang + ":" + ":".join(str(int(os.path.getmtime(p))) for p in files)
    cache = frappe.cache()
    messages = cache.get_value(key)
    if messages is None:
        messages = {}
        wanted = _spa_keys()
        for path in files:
            messages.update({k: v for k, v in _read_csv(path).items() if k in wanted})
        cache.set_value(key, messages)
    return messages


def get_asset_version():
    """Newest mtime under public/aida, used as a cache-busting query string."""
    newest = 0
    try:
        root = frappe.get_app_path("pibiassistant", "public", "aida")
        for folder, _dirs, names in os.walk(root):
            for name in names:
                newest = max(newest, int(os.path.getmtime(os.path.join(folder, name))))
    except OSError:
        return "0"
    return str(newest or 0)
