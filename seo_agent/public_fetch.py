"""GET-only public fetcher. Pin the socket address while retaining Host/SNI/TLS.

Resolution occurs both before the request and inside _new_conn. Every resolved
address must be public. The socket connects to a validated numeric sockaddr,
never a hostname; its peer is checked before HTTP/TLS bytes are sent.
"""
from __future__ import annotations

import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError

from .config import public_url

UA = "LocalSEOAudit/2.0 (authorized read-only audit)"
MAX_BYTES = 2 * 1024 * 1024


def public_address(address: str) -> bool:
    try:
        addr = ipaddress.ip_address(address)
    except ValueError:
        return False
    mapped = getattr(addr, "ipv4_mapped", None)
    # Transition mechanisms can embed private endpoints; reject rather than guess.
    return addr.is_global and not addr.is_multicast and not addr.is_reserved and not (mapped and not mapped.is_global) and not getattr(addr, "sixtofour", None) and not getattr(addr, "teredo", None)


def resolve_public(host: str, port: int):
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise ValueError("Public DNS resolution failed") from None
    if not addresses or any(not public_address(item[4][0]) for item in addresses):
        raise ValueError("DNS returned a prohibited destination")
    return addresses


def connect_public(host: str, port: int, timeout: float, socket_options=()):
    for family, kind, proto, _, address in resolve_public(host, port):
        sock = socket.socket(family, kind, proto)
        try:
            sock.settimeout(timeout)
            for option in socket_options or ():
                sock.setsockopt(*option)
            sock.connect(address)
            peer = sock.getpeername()[0]
            if not public_address(peer) or ipaddress.ip_address(peer) != ipaddress.ip_address(address[0]):
                raise ValueError("Connection destination changed")
            return sock
        except ValueError:
            sock.close()
            raise
        except OSError:
            sock.close()
    raise OSError("Public connection failed")


class PinnedConnection:
    def _new_conn(self):
        try:
            return connect_public(self.host, self.port, self.timeout, self.socket_options)
        except (OSError, ValueError):
            raise NewConnectionError(self, "Public destination validation/connection failed") from None


class PublicHTTPConnection(PinnedConnection, HTTPConnection):
    pass


class PublicHTTPSConnection(PinnedConnection, HTTPSConnection):
    pass


class PublicHTTPPool(HTTPConnectionPool):
    ConnectionCls = PublicHTTPConnection


class PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = PublicHTTPSConnection


class PublicAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        # Instance-local map; do not mutate urllib3's global pool registry.
        self.poolmanager.pool_classes_by_scheme = {"http": PublicHTTPPool, "https": PublicHTTPSPool}


class PublicFetcher:
    def __init__(self, root_url: str, *, max_requests=400, max_bytes=MAX_BYTES, timeout=20):
        self.root_url = public_url(root_url)
        self.host = urlsplit(self.root_url).netloc
        self.max_requests, self.max_bytes, self.timeout = max_requests, max_bytes, timeout
        self.requests_made = 0
        self.session = requests.Session()
        self.session.trust_env = False  # No proxy or ambient .netrc credentials.
        self.session.headers.clear()
        self.session.headers.update({"User-Agent": UA, "Accept-Encoding": "identity"})
        self.session.mount("http://", PublicAdapter(max_retries=0))
        self.session.mount("https://", PublicAdapter(max_retries=0))

    def get(self, url, *, rp=None, **_):
        for _redirect in range(6):
            url = public_url(url)
            if urlsplit(url).netloc != self.host or (rp is not None and not rp.can_fetch(UA, url)):
                raise ValueError("Request blocked by hostname boundary or robots.txt")
            resolve_public(urlsplit(url).hostname, urlsplit(url).port or (443 if urlsplit(url).scheme == "https" else 80))
            self.requests_made += 1
            if self.requests_made > self.max_requests:
                raise ValueError("Public request budget exhausted")
            response = None
            try:
                # Fresh connection: validate destination on every page/redirect.
                self.session.cookies.clear()
                start = time.monotonic()
                response = self.session.get(url, timeout=(5, self.timeout), allow_redirects=False, stream=True, verify=True, headers={"Connection": "close"})
                if response.status_code in (301, 302, 303, 307, 308):
                    target = response.headers.get("Location")
                    if not target:
                        raise ValueError("Redirect has no destination")
                    url = urljoin(url, target)
                    continue
                length = response.headers.get("Content-Length", "0")
                if int(length) > self.max_bytes:
                    raise ValueError("Public response exceeds size limit")
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > self.max_bytes or time.monotonic() - start > self.timeout:
                        raise ValueError("Public response exceeds size/time limit")
                    chunks.append(chunk)
                response._content = b"".join(chunks)
                response._content_consumed = True
                return response
            except requests.RequestException:
                raise ValueError("Public request failed; check network/TLS/site availability") from None
            finally:
                if response is not None:
                    response.close()
        raise ValueError("Too many public redirects")

    def close(self):
        self.session.close()
