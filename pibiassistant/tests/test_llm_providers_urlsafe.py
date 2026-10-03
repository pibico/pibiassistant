"""SSRF rules for provider base URLs, plus the DNS pin."""

import socket
import unittest
from unittest import mock

import frappe

from pibiassistant.pibiassistant_chat.api.chat.providers import ProviderConfigError, ProviderServerError, get_provider, http, urlsafe
from pibiassistant.pibiassistant_chat.api.chat.providers.urlsafe import validate_base_url
from pibiassistant.tests import _fakeserver as fs

_real_getaddrinfo = socket.getaddrinfo


def _gai(*addrs):
    return lambda host, port, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ad, port)) for ad in addrs]


class TestValidateBaseUrl(unittest.TestCase):
    def setUp(self):
        self._had = "pa_allow_private_llm_urls" in frappe.conf
        frappe.conf.pop("pa_allow_private_llm_urls", None)

    def tearDown(self):
        if self._had:
            frappe.conf.pa_allow_private_llm_urls = 1
        else:
            frappe.conf.pop("pa_allow_private_llm_urls", None)

    def bad(self, url, **kw):
        with self.assertRaises(ProviderConfigError, msg=url):
            validate_base_url(url, **kw)

    def test_private_and_special_literals_rejected(self):
        for url in (
            "https://127.0.0.1", "https://127.0.0.1:8443/v1", "https://10.1.2.3/v1", "https://172.16.0.9",
            "https://172.31.255.1", "https://192.168.1.10", "https://169.254.169.254/latest", "https://100.100.100.200",
            "https://100.64.0.1", "https://0.0.0.0", "https://[::1]/v1", "https://[::ffff:127.0.0.1]/v1",
            "https://[::ffff:10.0.0.1]", "https://[fd00:ec2::254]", "https://[fe80::1]", "https://[fc00::1]",
            "https://224.0.0.1", "https://[::7f00:1]", "https://[2002:7f00:1::1]",
        ):
            self.bad(url)

    def test_odd_literals_rejected(self):
        for url in ("https://2130706433", "https://0177.0.0.1", "https://0x7f.1", "https://127.1", "https://0x7f000001",
                    "https://1.2.3", "https://256.1.1.1"):
            self.bad(url, resolve=False)

    def test_structure_rules(self):
        for url in (
            "", "   ", "http://api.openai.com/v1", "ftp://api.openai.com", "api.openai.com/v1",
            "https://user:pw@api.openai.com/v1", "https://user@api.openai.com", "https://api.openai.com@evil.example/",
            "https://api.openai.com/v1?x=1", "https://api.openai.com/v1#frag", "https://api.openai.com:99999/v1",
            "https://api.openai.com\\@evil.example", "https://exa mple.com", "https://",
        ):
            self.bad(url, resolve=False)

    def test_public_names_ok_and_normalised(self):
        v = validate_base_url("https://API.openai.com/v1/chat/completions/", resolve=False)
        self.assertEqual(v["url"], "https://api.openai.com/v1")
        self.assertEqual((v["scheme"], v["host"], v["port"]), ("https", "api.openai.com", 443))
        self.assertEqual(validate_base_url("https://example.com:8443/v1/", resolve=False)["port"], 8443)
        self.assertEqual(validate_base_url("https://8.8.8.8/v1")["ips"], ["8.8.8.8"])

    def test_dns_all_addresses_checked(self):
        with mock.patch.object(urlsafe.socket, "getaddrinfo", _gai("8.8.8.8", "127.0.0.1")):
            self.bad("https://mixed.example")
        with mock.patch.object(urlsafe.socket, "getaddrinfo", _gai("8.8.8.8", "1.1.1.1")):
            self.assertEqual(validate_base_url("https://ok.example")["ips"], ["8.8.8.8", "1.1.1.1"])
        with mock.patch.object(urlsafe.socket, "getaddrinfo", _gai("10.0.0.5")):
            self.bad("https://internal.example")
        with mock.patch.object(urlsafe.socket, "getaddrinfo", side_effect=socket.gaierror):
            self.bad("https://nowhere.example")

    def test_flag_allows_private_but_never_link_local_or_metadata(self):
        validate_base_url("http://127.0.0.1:11434/v1", allow_private=True)
        validate_base_url("https://10.0.0.5/v1", allow_private=True)
        validate_base_url("http://[::1]:8000", allow_private=True)
        for url in ("http://169.254.169.254", "https://[fd00:ec2::254]", "http://100.100.100.200", "http://169.254.1.1",
                    "http://[fe80::1]", "http://0.0.0.0"):
            self.bad(url, allow_private=True)

    def test_flag_read_from_site_config(self):
        self.bad("http://127.0.0.1:1")
        frappe.conf.pa_allow_private_llm_urls = 1
        self.assertEqual(validate_base_url("http://127.0.0.1:1")["ips"], ["127.0.0.1"])

    def test_save_time_check_skips_dns_but_checks_literals(self):
        with mock.patch.object(urlsafe.socket, "getaddrinfo", side_effect=AssertionError("no DNS")):
            validate_base_url("https://anything.example/v1", resolve=False)
            self.bad("https://127.0.0.1", resolve=False)


class TestRequestPinning(fs.ServerCase):
    def test_localhost_name_sends_original_host_header(self):
        r = http.request({"slug": "x"}, "GET", f"http://localhost:{self.port}/v1/models",
                         headers={"Authorization": f"Bearer {fs.FAKE_KEY}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(fs.requests_log(self.port)[-1]["host"], f"localhost:{self.port}")

    def test_dns_rebinding_cannot_change_target(self):
        calls = []

        def gai(host, port, *a, **k):
            if host == "rebind.test":
                calls.append(host)
                ip = "127.0.0.1" if len(calls) == 1 else "8.8.8.8"
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
            return _real_getaddrinfo(host, port, *a, **k)

        with mock.patch.object(socket, "getaddrinfo", gai):
            r = http.request({"slug": "x"}, "GET", f"http://rebind.test:{self.port}/v1/models",
                             headers={"Authorization": f"Bearer {fs.FAKE_KEY}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(calls, ["rebind.test"])  # resolved exactly once, the connection used that answer
        self.assertEqual(fs.requests_log(self.port)[-1]["host"], f"rebind.test:{self.port}")

    def test_private_answer_rejected_without_flag(self):
        frappe.conf.pop("pa_allow_private_llm_urls", None)
        with mock.patch.object(socket, "getaddrinfo", _gai("127.0.0.1")):
            with self.assertRaises(ProviderConfigError):
                http.request({"slug": "x"}, "GET", f"https://rebind.test:{self.port}/v1/models", headers={})
        self.assertEqual(fs.requests_log(self.port), [])

    def test_redirect_is_refused_not_followed(self):
        a = get_provider(self.row("openai", "redirect"), key=fs.FAKE_KEY)
        with self.assertRaises(ProviderServerError) as cm:
            a.chat([{"role": "user", "content": "x"}])
        self.assertIn("redirect", str(cm.exception))
        self.assertEqual(len(self.posts()), 1)

    def test_url_checked_at_call_time(self):
        a = get_provider(self.row("openai", base_url="http://169.254.169.254/v1"), key=fs.FAKE_KEY)
        with self.assertRaises(ProviderConfigError):
            a.chat([{"role": "user", "content": "x"}])

    def test_pinned_adapter_keeps_hostname_for_tls(self):
        ad = urlsafe.PinnedAdapter("api.example.com")
        kw = ad.poolmanager.connection_pool_kw
        self.assertEqual(kw["server_hostname"], "api.example.com")
        self.assertEqual(kw["assert_hostname"], "api.example.com")


class TestAllowPrivateInThreads(unittest.TestCase):
    def test_flag_captured_in_request_thread_reaches_pool_threads(self):
        from concurrent.futures import ThreadPoolExecutor

        had = frappe.conf.get("pa_allow_private_llm_urls")
        frappe.conf.pa_allow_private_llm_urls = 1
        try:
            flag = urlsafe.allow_private_now()
            self.assertTrue(flag)
            probe = lambda: validate_base_url("http://127.0.0.1:9/v1", resolve=False)["url"]
            with ThreadPoolExecutor(max_workers=1) as pool:
                with self.assertRaises(ProviderConfigError):
                    pool.submit(probe).result()
                self.assertTrue(pool.submit(urlsafe.allow_private_scope(flag, probe)).result().startswith("http://"))
                # the override does not leak into the next job on the same thread
                with self.assertRaises(ProviderConfigError):
                    pool.submit(probe).result()
        finally:
            if had is None:
                frappe.conf.pop("pa_allow_private_llm_urls", None)
            else:
                frappe.conf.pa_allow_private_llm_urls = had
