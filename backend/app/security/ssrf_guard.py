from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_ip_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in BLOCKED_IP_NETWORKS)
    except ValueError:
        return True


def validate_outbound_url(url: str, allow_http: bool = False) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError("Invalid URL: Scheme and hostname required")

    scheme = parsed.scheme.lower()
    allowed_schemes = ("https", "http") if allow_http else ("https",)
    if scheme not in allowed_schemes:
        raise ValueError(f"Prohibited scheme '{scheme}'. Only HTTPS is allowed")

    hostname = parsed.hostname
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as err:
        raise ValueError(f"Could not resolve hostname '{hostname}'") from err

    resolved_ips = {addr[4][0] for addr in addr_info}
    for ip in resolved_ips:
        if is_ip_blocked(ip):
            raise ValueError(f"SSRF Protection: Access to blocked IP address '{ip}' is denied")

    return url
