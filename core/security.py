"""
Outbound URL Security (SSRF Guard)
====================================
Shared validation for any user-supplied URL the platform will make an
outbound request to (webhooks, callbacks). Used at creation time AND
immediately before dispatch — DNS must be re-checked at send time because
records can change between the two (rebinding).

Defence layers:
  1. Scheme/hostname blocklist (localhost, *.local, metadata hosts).
  2. Literal-IP checks (ipaddress) including inet_aton shorthand forms
     such as "127.1" or "0x7f000001" that ipaddress alone rejects.
  3. DNS resolution via getaddrinfo — EVERY resolved address must be a
     public, globally-routable IP or the URL is rejected (fail closed:
     unresolvable hosts are rejected too).
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

# Hostnames never allowed as outbound destinations (SSRF guard).
FORBIDDEN_HOST_SUFFIXES = (".local", ".internal", ".localhost", ".localdomain")
FORBIDDEN_HOSTS = {"localhost", "metadata", "metadata.google.internal", "ip6-localhost"}


def _is_forbidden_address(addr: ipaddress._BaseAddress) -> bool:
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def _literal_addresses(host: str) -> list[ipaddress._BaseAddress]:
    """Addresses for host without DNS: ipaddress + inet_aton shorthand forms."""
    found: list[ipaddress._BaseAddress] = []
    try:
        found.append(ipaddress.ip_address(host))
        return found
    except ValueError:
        pass
    # inet_aton accepts "127.1", "2130706433", "0x7f000001" (platform-dependent)
    try:
        packed = socket.inet_aton(host)
        found.append(ipaddress.ip_address(socket.inet_ntoa(packed)))
    except OSError:
        pass
    return found


async def validate_public_url(url: str) -> None:
    """
    Raise ValueError when *url* targets internal infrastructure.

    Resolves DNS (unless the host is a literal IP) and checks every resolved
    address. Async: uses the running loop's getaddrinfo so the event loop is
    not blocked by DNS.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("url has no hostname")
    if host in FORBIDDEN_HOSTS or host.endswith(FORBIDDEN_HOST_SUFFIXES):
        raise ValueError("url targets a forbidden internal host")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    candidates = _literal_addresses(host)
    if not candidates:
        try:
            try:
                loop = asyncio.get_running_loop()
                infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            except RuntimeError:  # no running loop (sync context)
                infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError(f"cannot resolve host: {host}") from exc
        for info in infos:
            try:
                candidates.append(ipaddress.ip_address(info[4][0]))
            except ValueError:
                continue
        if not candidates:
            raise ValueError(f"cannot resolve host: {host}")

    for addr in candidates:
        if _is_forbidden_address(addr):
            raise ValueError(f"url targets a private or internal address ({addr})")
