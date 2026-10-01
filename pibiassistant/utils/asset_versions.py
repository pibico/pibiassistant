"""Cache-busting for native ES modules.

nginx serves /assets with a one-year Cache-Control, and `import "./x.js"` cannot carry a
query string, so a changed module stays stale in browsers that already have it. An import
map that points every module URL at a content-hashed twin fixes that without a bundler.
"""

import hashlib
import os

import frappe

_cache: dict[str, tuple[int, dict[str, str]]] = {}


def module_import_map(public_subdir: str) -> dict[str, str]:
    """{"/assets/pibiassistant/<dir>/x.js": "/assets/pibiassistant/<dir>/x.js?v=<digest>"} for every .js below it."""
    try:
        root = frappe.get_app_path("pibiassistant", "public", *public_subdir.split("/"))
        files = []
        newest = 0
        for folder, _dirs, names in os.walk(root):
            for name in sorted(names):
                if name.endswith((".js", ".mjs")):
                    path = os.path.join(folder, name)
                    files.append(path)
                    newest = max(newest, int(os.path.getmtime(path)))
    except OSError:
        return {}
    hit = _cache.get(public_subdir)
    if hit and hit[0] == newest and len(hit[1]) == len(files):
        return hit[1]
    mapping = {}
    for path in files:
        url = "/assets/pibiassistant/" + public_subdir + "/" + os.path.relpath(path, root).replace(os.sep, "/")
        with open(path, "rb") as f:
            digest = hashlib.sha1(f.read()).hexdigest()[:10]
        mapping[url] = f"{url}?v={digest}"
    _cache[public_subdir] = (newest, mapping)
    return mapping
