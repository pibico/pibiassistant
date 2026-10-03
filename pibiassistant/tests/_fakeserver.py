"""Start/stop the local fake provider servers used by the provider tests."""

import json
import os
import subprocess
import sys
import threading
import time
import unittest
import urllib.request

FAKE_KEY = "sk-test-FAKE"
_DEFAULT_DIR = (
    "/tmp/claude-1000/-home-erpnext-erpnext-pibico/a9939f50-023b-4966-bbd3-e62bd00f71b6/scratchpad/fakeproviders"
)


def _dir():
    return os.environ.get("PA_FAKE_PROVIDERS_DIR") or _DEFAULT_DIR


def start(kind):
    """Spawn the fake server of this kind ("openai" | "anthropic"); returns (proc, port)."""
    script = os.path.join(_dir(), f"{kind}_fake.py")
    if not os.path.exists(script):
        raise unittest.SkipTest(f"fake provider server missing: {script}")
    proc = subprocess.Popen(
        [sys.executable, script, "--port", "0"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
    )
    holder = {}

    def read():
        holder["line"] = proc.stdout.readline()

    t = threading.Thread(target=read, daemon=True)
    t.start()
    t.join(10)
    line = holder.get("line", "")
    if not line.startswith("READY "):
        stop(proc)
        raise RuntimeError("fake provider server did not start")
    return proc, int(line.split()[1])


def stop(proc):
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        proc.stdout.close()
    except Exception:
        pass


def requests_log(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/__requests", timeout=5) as r:
        return json.loads(r.read().decode())


def reset(port):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/__reset", data=b"{}", method="POST")
    urllib.request.urlopen(req, timeout=5).read()


class ServerCase(unittest.TestCase):
    """Base for tests that talk to one fake server. Subclasses set KIND."""

    KIND = "openai"
    proc = None
    port = 0

    @classmethod
    def setUpClass(cls):
        cls.proc, cls.port = start(cls.KIND)

    @classmethod
    def tearDownClass(cls):
        if cls.proc:
            stop(cls.proc)

    def setUp(self):
        import frappe

        from pibiassistant.pibiassistant_chat.api.chat.providers import http

        self._had_flag = "pa_allow_private_llm_urls" in frappe.conf
        self._old_flag = frappe.conf.get("pa_allow_private_llm_urls")
        frappe.conf.pa_allow_private_llm_urls = 1
        self._old_delays = http.RETRY_DELAYS
        http.RETRY_DELAYS = (0.0, 0.0)
        reset(self.port)

    def tearDown(self):
        import frappe

        from pibiassistant.pibiassistant_chat.api.chat.providers import http

        http.RETRY_DELAYS = self._old_delays
        if self._had_flag:
            frappe.conf.pa_allow_private_llm_urls = self._old_flag
        else:
            frappe.conf.pop("pa_allow_private_llm_urls", None)

    def row(self, provider_id="openai", model="echo-1", **kw):
        base = f"http://127.0.0.1:{self.port}"
        if self.KIND == "openai" and provider_id != "azure_openai":
            base += "/v1"
        row = {
            "name": "ZZ-row", "provider_id": provider_id, "slug": provider_id.replace("_", "-"),
            "label": "ZZ Fake", "base_url": base, "default_model": model, "deployment": "",
            "api_version": "", "extra_models": [], "timeout_seconds": 120, "max_output_tokens": 0,
        }
        row.update(kw)
        return row

    def posts(self):
        return [r for r in requests_log(self.port) if r["method"] == "POST"]
