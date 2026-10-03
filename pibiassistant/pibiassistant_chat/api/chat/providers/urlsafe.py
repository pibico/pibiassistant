"""SSRF protection for admin-configured provider URLs.

Every outbound request resolves the host once, checks every address and then
connects to that exact address (open_pinned), so DNS rebinding between the
check and the connection cannot reach an internal service.
"""

import ipaddress
import json
import re
import socket
import threading
from urllib.parse import urlsplit

import frappe
import requests
from frappe import _
from requests.adapters import HTTPAdapter

from .errors import ProviderConfigError

METADATA_ADDRESSES = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00:ec2::254"),
    ipaddress.ip_address("100.100.100.200"),
}
_IPV4 = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")
_ODD_NUMERIC = re.compile(r"^(0x[0-9a-f]+|\d+)(\.(0x[0-9a-f]+|\d+))*$", re.I)
_DNS_NAME = re.compile(r"^[a-z0-9_]([a-z0-9_-]{0,62}[a-z0-9_])?(\.[a-z0-9_]([a-z0-9_-]{0,62}[a-z0-9_])?)*$")
_BAD_CHARS = re.compile(r"[\s\\\x00-\x1f\x7f]")


_override = threading.local()


def allow_private_now():
    """The site flag as read in the calling (request) thread, to hand to worker threads."""
    try:
        return bool(frappe.conf.get("pa_allow_private_llm_urls"))
    except Exception:
        return False


def _allow_private_default():
    # worker threads have no frappe.local: they run under allow_private_scope()
    forced = getattr(_override, "value", None)
    if forced is not None:
        return forced
    try:
        return bool(frappe.conf.get("pa_allow_private_llm_urls"))
    except Exception:
        return False


def allow_private_scope(value, fn):
    """Wrap fn so it runs with the private-URL flag fixed to value (for pool threads)."""

    def run():
        _override.value = value
        try:
            return fn()
        finally:
            _override.value = None

    return run


def _unwrap(ip):
    """Return the IPv4 address hidden inside a v6 one, if any."""
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            return ip.ipv4_mapped
        if ip.sixtofour:
            return ip.sixtofour
        if ip.teredo:
            return ip.teredo[1]
        n = int(ip)
        if 1 < n < 2**32:  # ::a.b.c.d (IPv4-compatible)
            return ipaddress.IPv4Address(n)
    return ip


def _check_ip(ip, allow_private):
    ip = _unwrap(ip)
    if (
        ip in METADATA_ADDRESSES
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or (ip.is_reserved and not ip.is_loopback)
    ):
        raise ProviderConfigError(_("The base URL points to a private or reserved address"))
    if not ip.is_global and not allow_private:
        raise ProviderConfigError(_("The base URL points to a private or reserved address"))


def _parse_host(parts):
    """Return (host, literal_ip_or_None); reject anything that is not a DNS name or a canonical literal."""
    netloc = parts.netloc
    host = parts.hostname
    if not host:
        raise ProviderConfigError(_("The base URL is not valid"))
    if netloc.startswith("["):
        try:
            return host, ipaddress.IPv6Address(host.split("%")[0])
        except ValueError:
            raise ProviderConfigError(_("The base URL is not valid")) from None
    host = host.rstrip(".")
    m = _IPV4.match(host)
    if m:
        octets = m.groups()
        if any(int(o) > 255 or (len(o) > 1 and o.startswith("0")) for o in octets):
            raise ProviderConfigError(_("The base URL is not valid"))
        return host, ipaddress.IPv4Address(host)
    if _ODD_NUMERIC.match(host) or not _DNS_NAME.match(host):
        raise ProviderConfigError(_("The base URL is not valid"))
    return host, None


def _validate(url, allow_private, resolve, strip_suffix):
    if allow_private is None:
        allow_private = _allow_private_default()
    url = (url or "").strip()
    if not url:
        raise ProviderConfigError(_("The base URL is not valid"))
    if _BAD_CHARS.search(url):
        raise ProviderConfigError(_("The base URL is not valid"))
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ProviderConfigError(_("The base URL is not valid")) from None
    scheme = (parts.scheme or "").lower()
    if scheme != "https" and not (scheme == "http" and allow_private):
        raise ProviderConfigError(_("The base URL must start with https://"))
    if "@" in parts.netloc or parts.username or parts.password:
        raise ProviderConfigError(_("The base URL must not contain credentials"))
    if parts.query or parts.fragment or "?" in url or "#" in url:
        raise ProviderConfigError(_("The base URL must not contain a query or a fragment"))
    if port is not None and not (0 < port < 65536):
        raise ProviderConfigError(_("The base URL is not valid"))
    host, literal = _parse_host(parts)
    port = port or (443 if scheme == "https" else 80)

    if literal is not None:
        _check_ip(literal, allow_private)
        ips = [str(literal)]
    elif resolve:
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except (socket.gaierror, UnicodeError, OSError):
            raise ProviderConfigError(_("The base URL host could not be resolved")) from None
        ips = []
        for info in infos:
            addr = info[4][0].split("%")[0]
            ip = ipaddress.ip_address(addr)
            _check_ip(ip, allow_private)
            if addr not in ips:
                ips.append(addr)
        if not ips:
            raise ProviderConfigError(_("The base URL host could not be resolved"))
    else:
        ips = []

    path = parts.path.rstrip("/")
    if strip_suffix and path.endswith("/chat/completions"):
        path = path[: -len("/chat/completions")].rstrip("/")
    netloc = parts.netloc.lower()
    return {"url": f"{scheme}://{netloc}{path}", "scheme": scheme, "host": host, "port": port, "ips": ips}


def validate_base_url(url, allow_private=None, resolve=True):
    return _validate(url, allow_private, resolve, strip_suffix=True)


def validate_request_url(url, allow_private=None, resolve=True):
    """Same checks for a full request URL (path and query allowed, nothing else changes)."""
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}{parts.path}"
    v = _validate(base, allow_private, resolve, strip_suffix=False)
    v["url"] = url
    return v


class PinnedAdapter(HTTPAdapter):
    """Connect to a fixed IP while keeping Host, SNI and certificate checks on the real host."""

    def __init__(self, host, **kw):
        self._pin_host = host
        super().__init__(**kw)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["server_hostname"] = self._pin_host
        pool_kwargs["assert_hostname"] = self._pin_host
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


def open_pinned(validated, method, url, *, headers, json_body=None, stream=False, timeout=(10, 120), data=None):
    """Send one request to validated["ips"][0]. Redirects are never followed."""
    if not validated.get("ips"):
        raise ProviderConfigError(_("The base URL host could not be resolved"))
    ip = validated["ips"][0]
    host = validated["host"]
    port = validated["port"]
    scheme = validated["scheme"]
    default_port = 443 if scheme == "https" else 80
    parts = urlsplit(url)
    ip_literal = f"[{ip}]" if ":" in ip else ip
    netloc = f"{ip_literal}:{port}"
    pinned_url = parts._replace(netloc=netloc).geturl()
    hdrs = dict(headers or {})
    hdrs["Host"] = host if port == default_port else f"{host}:{port}"
    if ":" in host:
        hdrs["Host"] = f"[{host}]" + ("" if port == default_port else f":{port}")
    session = requests.Session()
    session.trust_env = False
    if scheme == "https":
        session.mount("https://", PinnedAdapter(host))
    try:
        if data is None and json_body is not None:
            data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        req = requests.Request(method, pinned_url, headers=hdrs, data=data)
        prepared = session.prepare_request(req)
        resp = session.send(
            prepared, stream=True, timeout=timeout, allow_redirects=False, verify=True, proxies={}
        )
    except Exception:
        session.close()
        raise
    orig_close = resp.close

    def close():
        orig_close()
        session.close()

    resp.close = close
    return resp
